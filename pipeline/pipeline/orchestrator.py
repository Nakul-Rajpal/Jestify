"""Pipeline orchestrator -- coordinates all four rendering stages."""

import logging
import tempfile
from pathlib import Path
from typing import Callable, Optional

from shared.contracts.enums import JobStatus
from shared.contracts.pipeline_schema import (
    PipelineInput,
    PipelineOutput,
    SceneInstruction,
)

from pipeline.config import ASSETS_PATH
from pipeline.manim_renderer.scene_builder import SceneBuilder
from pipeline.manim_renderer.renderer import ManimRenderer
from pipeline.voice_synth.synthesizer import VoiceSynthesizer
from pipeline.character_overlay.compositor import CharacterCompositor
from pipeline.character_overlay.animation_states import get_sprite_path
from pipeline.video_assembler.assembler import VideoAssembler
from pipeline.utils.ffmpeg_helpers import get_video_duration

logger = logging.getLogger(__name__)

StatusCallback = Callable[[JobStatus, int], None]


class PipelineOrchestrator:
    """Coordinates the four sequential stages of video generation.

    Stages
    ------
    1. ManimGL rendering   (all scenes)
    2. Voice synthesis      (all scenes)
    3. Character overlay    (all scenes)
    4. Final video assembly
    """

    def __init__(self, status_callback: Optional[StatusCallback] = None):
        self._on_progress = status_callback or (lambda _s, _p: None)
        self._scene_builder = SceneBuilder()
        self._renderer = ManimRenderer()
        self._voice_synth = VoiceSynthesizer()
        self._compositor = CharacterCompositor()
        self._assembler = VideoAssembler()

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def run(self, pipeline_input: PipelineInput) -> PipelineOutput:
        """Execute the full pipeline and return a ``PipelineOutput``."""

        script = pipeline_input.script
        character = pipeline_input.character
        scenes = script.scenes
        total_scenes = len(scenes)

        with tempfile.TemporaryDirectory(prefix=f"jestify_{pipeline_input.job_id}_") as tmpdir:
            tmp = Path(tmpdir)

            # ---- Stage 1: ManimGL rendering ------------------------------ #
            self._on_progress(JobStatus.RENDERING_ANIMATIONS, 0)
            animation_clips: list[str] = []
            for idx, scene in enumerate(scenes):
                clip_path = self._render_scene(scene, tmp, idx)
                animation_clips.append(clip_path)
                pct = int(((idx + 1) / total_scenes) * 25)
                self._on_progress(JobStatus.RENDERING_ANIMATIONS, pct)

            # ---- Stage 2: Voice synthesis -------------------------------- #
            self._on_progress(JobStatus.SYNTHESIZING_VOICE, 25)
            audio_clips: list[str] = []
            for idx, scene in enumerate(scenes):
                audio_path = str(tmp / f"voice_{idx:03d}.wav")
                self._voice_synth.synthesize(
                    text=scene.narration_text,
                    character_id=character.value,
                    output_path=audio_path,
                )
                audio_clips.append(audio_path)
                pct = 25 + int(((idx + 1) / total_scenes) * 25)
                self._on_progress(JobStatus.SYNTHESIZING_VOICE, pct)

            # ---- Stage 3: Character overlay compositing ------------------ #
            self._on_progress(JobStatus.COMPOSITING, 50)
            composited_clips: list[str] = []
            for idx, scene in enumerate(scenes):
                sprite_path = get_sprite_path(character.value, scene.character_action)
                composited_path = str(tmp / f"composited_{idx:03d}.mp4")
                self._compositor.composite(
                    animation_clip=animation_clips[idx],
                    character_sprite=sprite_path,
                    audio_file=audio_clips[idx],
                    output_path=composited_path,
                )
                composited_clips.append(composited_path)
                pct = 50 + int(((idx + 1) / total_scenes) * 25)
                self._on_progress(JobStatus.COMPOSITING, pct)

            # ---- Stage 4: Final assembly --------------------------------- #
            self._on_progress(JobStatus.ASSEMBLING, 75)
            output_path = pipeline_input.output_path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            self._assembler.assemble(
                scene_clips=composited_clips,
                output_path=output_path,
                intro_title=script.title,
            )
            self._on_progress(JobStatus.ASSEMBLING, 95)

            # ---- Compute final duration ---------------------------------- #
            try:
                duration = get_video_duration(output_path)
            except Exception:
                duration = sum(s.duration_hint_seconds for s in scenes)

        self._on_progress(JobStatus.COMPLETED, 100)

        return PipelineOutput(
            job_id=pipeline_input.job_id,
            video_path=output_path,
            duration_seconds=duration,
        )

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _render_scene(
        self, scene: SceneInstruction, tmp: Path, idx: int
    ) -> str:
        """Build a ManimGL scene file, render it, and return the clip path."""
        scene_py = str(tmp / f"scene_{idx:03d}.py")
        class_name = self._scene_builder.build_scene_file(scene, scene_py)
        clip_path = self._renderer.render_scene(scene_py, class_name)
        return clip_path
