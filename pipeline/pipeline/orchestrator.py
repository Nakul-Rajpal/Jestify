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

        logger.info("[orchestrator] Starting pipeline for job %s", pipeline_input.job_id)
        logger.info("[orchestrator] Character: %s", character.value)
        logger.info("[orchestrator] Total scenes: %d", total_scenes)
        logger.info("[orchestrator] Scene types: %s", [s.manim_scene_type for s in scenes])
        logger.info("[orchestrator] Output path: %s", pipeline_input.output_path)

        with tempfile.TemporaryDirectory(prefix=f"jestify_{pipeline_input.job_id}_") as tmpdir:
            tmp = Path(tmpdir)
            logger.info("[orchestrator] Temp directory: %s", tmp)

            # ---- Stage 1: ManimGL rendering ------------------------------ #
            logger.info("[orchestrator] === STAGE 1: ManimGL Rendering ===")
            self._on_progress(JobStatus.RENDERING_ANIMATIONS, 0)

            # Track succeeded scenes so failed ones are skipped gracefully.
            rendered: list[tuple[SceneInstruction, str]] = []
            for idx, scene in enumerate(scenes):
                logger.info("[orchestrator] Rendering scene %d/%d (type: %s)", idx + 1, total_scenes, scene.manim_scene_type)
                try:
                    clip_path = self._render_scene(scene, tmp, idx)
                    rendered.append((scene, clip_path))
                    logger.info("[orchestrator] Scene %d rendered: %s", idx + 1, clip_path)
                except Exception as e:
                    logger.error("[orchestrator] Scene %d FAILED (skipping): %s", idx + 1, str(e))
                pct = int(((idx + 1) / total_scenes) * 25)
                self._on_progress(JobStatus.RENDERING_ANIMATIONS, pct)

            if not rendered:
                raise RuntimeError("All scenes failed to render")

            logger.info(
                "[orchestrator] %d/%d scenes rendered successfully",
                len(rendered), total_scenes,
            )

            # ---- Stage 2: Voice synthesis -------------------------------- #
            logger.info("[orchestrator] === STAGE 2: Voice Synthesis ===")
            self._on_progress(JobStatus.SYNTHESIZING_VOICE, 25)
            audio_clips: list[str] = []
            for idx, (scene, _clip) in enumerate(rendered):
                audio_path = str(tmp / f"voice_{idx:03d}.wav")
                logger.info("[orchestrator] Synthesizing voice %d/%d (%d chars of text)", idx + 1, len(rendered), len(scene.narration_text))
                self._voice_synth.synthesize(
                    text=scene.narration_text,
                    character_id=character.value,
                    output_path=audio_path,
                )
                audio_clips.append(audio_path)
                logger.info("[orchestrator] Voice %d synthesized: %s", idx + 1, audio_path)
                pct = 25 + int(((idx + 1) / len(rendered)) * 25)
                self._on_progress(JobStatus.SYNTHESIZING_VOICE, pct)

            # ---- Stage 3: Character overlay compositing ------------------ #
            logger.info("[orchestrator] === STAGE 3: Character Overlay ===")
            self._on_progress(JobStatus.COMPOSITING, 50)
            composited_clips: list[str] = []
            for idx, (scene, anim_clip) in enumerate(rendered):
                sprite_path = get_sprite_path(character.value, scene.character_action)
                composited_path = str(tmp / f"composited_{idx:03d}.mp4")
                logger.info("[orchestrator] Compositing scene %d/%d (sprite: %s)", idx + 1, len(rendered), sprite_path)
                self._compositor.composite(
                    animation_clip=anim_clip,
                    character_sprite=sprite_path,
                    audio_file=audio_clips[idx],
                    output_path=composited_path,
                )
                composited_clips.append(composited_path)
                logger.info("[orchestrator] Scene %d composited: %s", idx + 1, composited_path)
                pct = 50 + int(((idx + 1) / len(rendered)) * 25)
                self._on_progress(JobStatus.COMPOSITING, pct)

            # ---- Stage 4: Final assembly --------------------------------- #
            logger.info("[orchestrator] === STAGE 4: Final Assembly ===")
            self._on_progress(JobStatus.ASSEMBLING, 75)
            output_path = pipeline_input.output_path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            logger.info("[orchestrator] Assembling %d clips into: %s", len(composited_clips), output_path)

            self._assembler.assemble(
                scene_clips=composited_clips,
                output_path=output_path,
                intro_title=script.title,
            )
            self._on_progress(JobStatus.ASSEMBLING, 95)
            logger.info("[orchestrator] Assembly complete")

            # ---- Compute final duration ---------------------------------- #
            try:
                duration = get_video_duration(output_path)
                logger.info("[orchestrator] Final video duration: %.1f seconds", duration)
            except Exception as e:
                logger.warning("[orchestrator] Could not get video duration: %s", e)
                duration = sum(s.duration_hint_seconds for s, _ in rendered)
                logger.info("[orchestrator] Using estimated duration: %.1f seconds", duration)

        self._on_progress(JobStatus.COMPLETED, 100)
        logger.info("[orchestrator] Pipeline complete for job %s", pipeline_input.job_id)

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
        logger.info("[orchestrator] Building scene file: %s", scene_py)
        class_name = self._scene_builder.build_scene_file(scene, scene_py)
        logger.info("[orchestrator] Built scene class: %s", class_name)
        clip_path = self._renderer.render_scene(scene_py, class_name)
        return clip_path
