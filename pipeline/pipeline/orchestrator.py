"""Pipeline orchestrator -- coordinates all four rendering stages."""

import logging
import re
import tempfile
import time
import traceback
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

MAX_RENDER_RETRIES = 3
MAX_FAILED_SCENES_BEFORE_ABORT = 4


class PipelineOrchestrator:
    """Coordinates the four sequential stages of video generation."""

    def __init__(self, status_callback: Optional[StatusCallback] = None):
        self._on_progress = status_callback or (lambda _s, _p: None)
        self._scene_builder = SceneBuilder()
        self._renderer = ManimRenderer()
        self._voice_synth = VoiceSynthesizer()
        self._compositor = CharacterCompositor()
        self._assembler = VideoAssembler()

    def run(self, pipeline_input: PipelineInput) -> PipelineOutput:
        """Execute the full pipeline and return a ``PipelineOutput``."""

        script = pipeline_input.script
        character = pipeline_input.character
        scenes = script.scenes
        total_scenes = len(scenes)
        pipeline_t0 = time.perf_counter()

        logger.info("=" * 70)
        logger.info("[orchestrator] PIPELINE START — job %s", pipeline_input.job_id)
        logger.info("=" * 70)
        logger.info("[orchestrator] Character: %s", character.value)
        logger.info("[orchestrator] Total scenes: %d", total_scenes)
        logger.info("[orchestrator] Script title: %s", script.title)
        logger.info("[orchestrator] Output path: %s", pipeline_input.output_path)
        for i, s in enumerate(scenes):
            has_code = bool(s.manim_code)
            logger.info(
                "[orchestrator]   Scene %d: type=%s, duration_hint=%.0fs, has_code=%s, action=%s",
                i + 1, s.manim_scene_type, s.duration_hint_seconds,
                has_code, s.character_action,
            )

        with tempfile.TemporaryDirectory(prefix=f"jestify_{pipeline_input.job_id}_") as tmpdir:
            tmp = Path(tmpdir)
            logger.info("[orchestrator] Temp directory: %s", tmp)

            # ── Stage 1: Manim rendering ───────────────────────────────── #
            logger.info("[orchestrator] ══ STAGE 1/4: Manim Rendering ══")
            self._on_progress(JobStatus.RENDERING_ANIMATIONS, 20)
            stage_t0 = time.perf_counter()

            rendered: list[tuple[SceneInstruction, str]] = []
            failed_scenes: list[tuple[int, str]] = []
            for idx, scene in enumerate(scenes):
                scene_t0 = time.perf_counter()
                logger.info(
                    "[orchestrator] ── Rendering scene %d/%d (type: %s, hint: %.0fs)",
                    idx + 1, total_scenes, scene.manim_scene_type,
                    scene.duration_hint_seconds,
                )

                clip_path = None
                last_error = ""
                for attempt in range(1, MAX_RENDER_RETRIES + 1):
                    try:
                        clip_path = self._render_scene(scene, tmp, idx, attempt)
                        break
                    except Exception as e:
                        last_error = str(e)
                        err_lower = last_error.lower()
                        logger.error(
                            "[orchestrator] Attempt %d/%d failed for scene %d: %s",
                            attempt, MAX_RENDER_RETRIES, idx + 1, e,
                        )
                        if scene.manim_code:
                            # Detect LaTeX/rendering errors (dvi, svg, latex, cache, tex)
                            is_latex_error = any(
                                kw in err_lower
                                for kw in ("dvi", "svg", "latex", "cache", "tex(", "typeerror")
                            )
                            if is_latex_error and attempt == 1:
                                sanitized = self._sanitize_latex_to_text(scene.manim_code)
                                if sanitized != scene.manim_code:
                                    scene.manim_code = sanitized
                                    logger.warning(
                                        "[orchestrator] Scene %d: sanitized Tex→Text, retrying",
                                        idx + 1,
                                    )
                                else:
                                    scene.manim_code = None
                                    logger.warning(
                                        "[orchestrator] Scene %d: sanitization unchanged, falling back to template",
                                        idx + 1,
                                    )
                            else:
                                # Any other error or repeated failure: drop LLM code
                                scene.manim_code = None
                                logger.warning(
                                    "[orchestrator] Scene %d: LLM code failed (attempt %d), falling back to template",
                                    idx + 1, attempt,
                                )
                        if attempt < MAX_RENDER_RETRIES:
                            logger.info("[orchestrator] Retrying scene %d...", idx + 1)

                if clip_path:
                    elapsed = time.perf_counter() - scene_t0
                    clip_size = Path(clip_path).stat().st_size / (1024 * 1024)
                    rendered.append((scene, clip_path))
                    logger.info(
                        "[orchestrator] ✓ Scene %d OK: %s (%.1f MB, %.1fs)",
                        idx + 1, clip_path, clip_size, elapsed,
                    )
                else:
                    elapsed = time.perf_counter() - scene_t0
                    failed_scenes.append((idx + 1, last_error))
                    logger.error(
                        "[orchestrator] ✗ Scene %d FAILED after %d attempts (%.1fs): %s",
                        idx + 1, MAX_RENDER_RETRIES, elapsed, last_error[:200],
                    )

                pct = 20 + int(((idx + 1) / total_scenes) * 20)
                self._on_progress(JobStatus.RENDERING_ANIMATIONS, pct)

            stage_elapsed = time.perf_counter() - stage_t0
            logger.info(
                "[orchestrator] Stage 1 complete: %d/%d rendered, %d failed (%.1fs)",
                len(rendered), total_scenes, len(failed_scenes), stage_elapsed,
            )
            if failed_scenes:
                for scene_num, err in failed_scenes:
                    logger.error("[orchestrator]   Failed scene %d: %s", scene_num, err[:200])

            if not rendered:
                raise RuntimeError(
                    f"All {total_scenes} scenes failed to render. "
                    f"Errors: {[f'Scene {n}: {e[:100]}' for n, e in failed_scenes]}"
                )
            if len(failed_scenes) > MAX_FAILED_SCENES_BEFORE_ABORT:
                raise RuntimeError(
                    f"Too many scene failures ({len(failed_scenes)}/{total_scenes}). "
                    f"Aborting video generation because more than {MAX_FAILED_SCENES_BEFORE_ABORT} "
                    "scene renders failed."
                )

            # ── Stage 2: Voice synthesis ────────────────────────────────── #
            logger.info("[orchestrator] ══ STAGE 2/4: Voice Synthesis ══")
            self._on_progress(JobStatus.SYNTHESIZING_VOICE, 40)
            stage_t0 = time.perf_counter()

            audio_clips: list[str] = []
            for idx, (scene, _clip) in enumerate(rendered):
                voice_t0 = time.perf_counter()
                audio_path = str(tmp / f"voice_{idx:03d}.wav")
                logger.info(
                    "[orchestrator] Synthesizing voice %d/%d: %d chars",
                    idx + 1, len(rendered), len(scene.narration_text),
                )
                try:
                    self._voice_synth.synthesize(
                        text=scene.narration_text,
                        character_id=character.value,
                        output_path=audio_path,
                        voice_id=pipeline_input.voice_id,
                    )
                    audio_size = Path(audio_path).stat().st_size / 1024
                    elapsed = time.perf_counter() - voice_t0
                    audio_clips.append(audio_path)
                    logger.info(
                        "[orchestrator] ✓ Voice %d OK: %.1f KB, %.1fs",
                        idx + 1, audio_size, elapsed,
                    )
                except Exception as e:
                    logger.error("[orchestrator] ✗ Voice %d FAILED: %s", idx + 1, e)
                    logger.error("[orchestrator]   Traceback:\n%s", traceback.format_exc())
                    raise
                pct = 40 + int(((idx + 1) / len(rendered)) * 20)
                self._on_progress(JobStatus.SYNTHESIZING_VOICE, pct)

            stage_elapsed = time.perf_counter() - stage_t0
            logger.info("[orchestrator] Stage 2 complete: %d audio clips (%.1fs)", len(audio_clips), stage_elapsed)

            # ── Stage 3: Character overlay ──────────────────────────────── #
            logger.info("[orchestrator] ══ STAGE 3/4: Character Overlay ══")
            self._on_progress(JobStatus.COMPOSITING, 60)
            stage_t0 = time.perf_counter()

            composited_clips: list[str] = []
            for idx, (scene, anim_clip) in enumerate(rendered):
                comp_t0 = time.perf_counter()
                sprite_path = get_sprite_path(character.value, scene.character_action)
                composited_path = str(tmp / f"composited_{idx:03d}.mp4")
                logger.info(
                    "[orchestrator] Compositing scene %d/%d", idx + 1, len(rendered),
                )
                try:
                    self._compositor.composite(
                        animation_clip=anim_clip,
                        character_sprite=sprite_path,
                        audio_file=audio_clips[idx],
                        output_path=composited_path,
                    )
                    comp_size = Path(composited_path).stat().st_size / (1024 * 1024)
                    elapsed = time.perf_counter() - comp_t0
                    composited_clips.append(composited_path)
                    logger.info(
                        "[orchestrator] ✓ Composite %d OK: %.1f MB, %.1fs",
                        idx + 1, comp_size, elapsed,
                    )
                except Exception as e:
                    logger.error("[orchestrator] ✗ Composite %d FAILED: %s", idx + 1, e)
                    logger.error("[orchestrator]   Traceback:\n%s", traceback.format_exc())
                    raise
                pct = 60 + int(((idx + 1) / len(rendered)) * 20)
                self._on_progress(JobStatus.COMPOSITING, pct)

            stage_elapsed = time.perf_counter() - stage_t0
            logger.info("[orchestrator] Stage 3 complete: %d clips (%.1fs)", len(composited_clips), stage_elapsed)

            # ── Stage 4: Final assembly ──────────────────────────────────── #
            logger.info("[orchestrator] ══ STAGE 4/4: Final Assembly ══")
            self._on_progress(JobStatus.ASSEMBLING, 80)
            stage_t0 = time.perf_counter()

            output_path = pipeline_input.output_path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            logger.info("[orchestrator] Assembling %d clips -> %s", len(composited_clips), output_path)

            try:
                self._assembler.assemble(
                    scene_clips=composited_clips,
                    output_path=output_path,
                    intro_title=script.title,
                )
            except Exception as e:
                logger.error("[orchestrator] ✗ Assembly FAILED: %s", e)
                logger.error("[orchestrator]   Traceback:\n%s", traceback.format_exc())
                raise

            self._on_progress(JobStatus.ASSEMBLING, 95)
            stage_elapsed = time.perf_counter() - stage_t0
            logger.info("[orchestrator] Stage 4 complete (%.1fs)", stage_elapsed)

            # ── Compute final duration ───────────────────────────────────── #
            try:
                duration = get_video_duration(output_path)
                final_size = Path(output_path).stat().st_size / (1024 * 1024)
                logger.info("[orchestrator] Final video: %.1fs, %.1f MB", duration, final_size)
            except Exception as e:
                logger.warning("[orchestrator] Could not probe duration: %s", e)
                duration = sum(s.duration_hint_seconds for s, _ in rendered)
                logger.info("[orchestrator] Using estimated duration: %.1fs", duration)

        pipeline_elapsed = time.perf_counter() - pipeline_t0
        self._on_progress(JobStatus.COMPLETED, 100)
        logger.info("=" * 70)
        logger.info(
            "[orchestrator] PIPELINE COMPLETE — job %s — %.1fs total",
            pipeline_input.job_id, pipeline_elapsed,
        )
        logger.info("=" * 70)

        return PipelineOutput(
            job_id=pipeline_input.job_id,
            video_path=output_path,
            duration_seconds=duration,
        )

    @staticmethod
    def _sanitize_latex_to_text(code: str) -> str:
        """Replace MathTex/Tex calls with Text equivalents, preserving all other code."""
        def _mathtex_to_text(m: re.Match) -> str:
            func = m.group(1)
            content = m.group(2)
            clean = content.strip().strip("r").strip("'\"").strip()
            clean = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", clean)
            clean = re.sub(r"\\begin\{[^}]*\}", "", clean)
            clean = re.sub(r"\\end\{[^}]*\}", "", clean)
            clean = re.sub(r"\\\\", " ", clean)
            clean = re.sub(r"[\\{}^_&]", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()
            if not clean:
                clean = "..."
            return f'Text("{clean}", font_size=36)'

        result = re.sub(
            r'\b(MathTex|Tex)\s*\(\s*(r?(?:"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"]*"|\'[^\']*\'))\s*\)',
            _mathtex_to_text,
            code,
        )
        result = re.sub(r'\bTransformMatchingTex\b', 'ReplacementTransform', result)
        return result

    def _render_scene(
        self, scene: SceneInstruction, tmp: Path, idx: int, attempt: int
    ) -> str:
        """Build a Manim scene file, render it, and return the clip path."""
        scene_py = str(tmp / f"scene_{idx:03d}_v{attempt}.py")
        logger.info("[orchestrator] Building scene file: %s (attempt %d)", scene_py, attempt)
        logger.info("[orchestrator]   Scene type: %s", scene.manim_scene_type)
        logger.info("[orchestrator]   Has LLM code: %s", bool(scene.manim_code))

        class_name = self._scene_builder.build_scene_file(scene, scene_py)
        logger.info("[orchestrator] Built scene class: %s", class_name)
        clip_path = self._renderer.render_scene(scene_py, class_name)
        return clip_path
