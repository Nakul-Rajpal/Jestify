"""Pipeline orchestrator -- coordinates all four rendering stages.

Stages 1 (Manim rendering) and 2 (voice synthesis) run concurrently because
voice synthesis only needs narration text, not the rendered video.  Within each
stage, scenes are processed in parallel using a thread pool.

When LLM-generated Manim code fails to render, the orchestrator asks Claude to
fix the code based on the error instead of falling back to a static template.
"""

import json
import logging
import os
import re
import tempfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional

import anthropic

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

MAX_RENDER_RETRIES = 4
MAX_FAILED_SCENES_BEFORE_ABORT = 4
_CODE_FIX_MODEL = "claude-sonnet-4-20250514"

def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except Exception:
        return default


# Concurrency limits (configurable via env)
MAX_RENDER_WORKERS = _env_int("MAX_RENDER_WORKERS", 4)      # CPU-bound (Manim subprocesses)
MAX_VOICE_WORKERS = _env_int("MAX_VOICE_WORKERS", 8)        # Network-bound (Fish Audio API)
MAX_COMPOSITE_WORKERS = _env_int("MAX_COMPOSITE_WORKERS", 3)  # CPU-bound (FFmpeg subprocesses)


class PipelineOrchestrator:
    """Coordinates video generation with parallel scene processing."""

    def __init__(self, status_callback: Optional[StatusCallback] = None):
        self._on_progress = status_callback or (lambda _s, _p: None)
        self._scene_builder = SceneBuilder()
        self._renderer = ManimRenderer()
        self._voice_synth = VoiceSynthesizer()
        self._compositor = CharacterCompositor()
        self._assembler = VideoAssembler()

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

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
        logger.info("[orchestrator] Parallelism: render=%d, voice=%d, composite=%d",
                     MAX_RENDER_WORKERS, MAX_VOICE_WORKERS, MAX_COMPOSITE_WORKERS)
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

            # ── Stages 1+2: Manim rendering & voice synthesis (CONCURRENT) ── #
            logger.info("[orchestrator] ══ STAGES 1+2: Rendering + Voice (parallel) ══")
            self._on_progress(JobStatus.RENDERING_ANIMATIONS, 15)
            stages_12_t0 = time.perf_counter()

            rendered, failed_scenes, audio_clips = self._run_render_and_voice(
                scenes, character.value, tmp, pipeline_input.voice_id, total_scenes,
            )

            stages_12_elapsed = time.perf_counter() - stages_12_t0
            logger.info(
                "[orchestrator] Stages 1+2 complete: %d/%d rendered, %d failed, %d audio (%.1fs)",
                len(rendered), total_scenes, len(failed_scenes), len(audio_clips),
                stages_12_elapsed,
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

            # ── Stage 3: Character overlay (parallel) ────────────────────── #
            logger.info("[orchestrator] ══ STAGE 3/4: Character Overlay (parallel) ══")
            self._on_progress(JobStatus.COMPOSITING, 60)
            stage3_t0 = time.perf_counter()

            composited_clips = self._run_compositing(
                rendered, audio_clips, character.value, tmp,
            )

            stage3_elapsed = time.perf_counter() - stage3_t0
            logger.info("[orchestrator] Stage 3 complete: %d clips (%.1fs)",
                        len(composited_clips), stage3_elapsed)

            # ── Stage 4: Final assembly ──────────────────────────────────── #
            logger.info("[orchestrator] ══ STAGE 4/4: Final Assembly ══")
            self._on_progress(JobStatus.ASSEMBLING, 80)
            stage4_t0 = time.perf_counter()

            output_path = pipeline_input.output_path
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            logger.info("[orchestrator] Assembling %d clips -> %s",
                        len(composited_clips), output_path)

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
            stage4_elapsed = time.perf_counter() - stage4_t0
            logger.info("[orchestrator] Stage 4 complete (%.1fs)", stage4_elapsed)

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

    # ------------------------------------------------------------------ #
    # Stages 1+2: Rendering + Voice (concurrent)
    # ------------------------------------------------------------------ #

    def _run_render_and_voice(
        self,
        scenes: list,
        character_id: str,
        tmp: Path,
        voice_id: Optional[str],
        total_scenes: int,
    ) -> tuple[list[tuple[SceneInstruction, str]], list[tuple[int, str]], list[str]]:
        """Run Manim rendering and voice synthesis concurrently.

        Returns (rendered, failed_scenes, audio_clips) where:
        - rendered: list of (scene, clip_path) for successfully rendered scenes
        - failed_scenes: list of (scene_number, error_message)
        - audio_clips: dict mapping scene index -> audio file path
        """
        # Results storage (thread-safe via GIL for simple appends)
        render_results: dict[int, Optional[str]] = {}  # idx -> clip_path or None
        render_errors: dict[int, str] = {}              # idx -> error message
        voice_results: dict[int, str] = {}              # idx -> audio_path
        voice_errors: dict[int, Exception] = {}         # idx -> exception

        progress_lock = threading.Lock()
        completed_renders = [0]
        completed_voices = [0]

        def _update_combined_progress():
            with progress_lock:
                render_pct = completed_renders[0] / total_scenes
                voice_pct = completed_voices[0] / total_scenes
                # Stages 1+2 occupy progress range 15-55%
                combined = 15 + int((render_pct * 0.6 + voice_pct * 0.4) * 40)
                if render_pct < 1.0:
                    self._on_progress(JobStatus.RENDERING_ANIMATIONS, combined)
                else:
                    self._on_progress(JobStatus.SYNTHESIZING_VOICE, combined)

        pool_size = MAX_RENDER_WORKERS + MAX_VOICE_WORKERS
        # Use a semaphore to limit concurrent Manim renders (CPU-bound)
        render_semaphore = threading.Semaphore(MAX_RENDER_WORKERS)

        with ThreadPoolExecutor(max_workers=pool_size) as pool:
            # Submit render jobs
            def _render_job(idx, scene):
                with render_semaphore:
                    return self._render_scene_with_retries(scene, tmp, idx, total_scenes)

            render_futures = {
                pool.submit(_render_job, idx, scene): idx
                for idx, scene in enumerate(scenes)
            }

            # Submit voice jobs (all at once — network-bound)
            voice_futures = {
                pool.submit(
                    self._synthesize_one_voice,
                    scene, character_id, tmp, idx, voice_id, total_scenes,
                ): idx
                for idx, scene in enumerate(scenes)
            }

            # Collect render results
            for future in as_completed(render_futures):
                idx = render_futures[future]
                try:
                    clip_path = future.result()
                    render_results[idx] = clip_path
                except Exception as e:
                    render_results[idx] = None
                    render_errors[idx] = str(e)
                completed_renders[0] += 1
                _update_combined_progress()

            # Collect voice results
            for future in as_completed(voice_futures):
                idx = voice_futures[future]
                try:
                    audio_path = future.result()
                    voice_results[idx] = audio_path
                except Exception as e:
                    voice_errors[idx] = e
                completed_voices[0] += 1
                _update_combined_progress()

        # If any voice synthesis failed, raise the first error
        if voice_errors:
            first_idx = min(voice_errors.keys())
            exc = voice_errors[first_idx]
            logger.error("[orchestrator] ✗ Voice %d FAILED: %s", first_idx + 1, exc)
            raise exc

        # Build ordered results (only include scenes that rendered successfully)
        rendered: list[tuple[SceneInstruction, str]] = []
        failed_scenes: list[tuple[int, str]] = []
        audio_clips: list[str] = []

        for idx in range(total_scenes):
            clip_path = render_results.get(idx)
            if clip_path:
                rendered.append((scenes[idx], clip_path))
                audio_clips.append(voice_results[idx])
            else:
                err = render_errors.get(idx, "Unknown render error")
                failed_scenes.append((idx + 1, err))

        return rendered, failed_scenes, audio_clips

    def _render_scene_with_retries(
        self, scene: SceneInstruction, tmp: Path, idx: int, total_scenes: int,
    ) -> str:
        """Render a single scene with retry logic.

        Retry strategy (NEVER falls back to static templates):
          1. Try the original LLM code
          2. If LaTeX error → sanitize MathTex→Text, retry
          3. If any error → ask Claude to fix the code based on the error, retry
          4. Last attempt with the LLM-fixed code
        """
        scene_t0 = time.perf_counter()
        logger.info(
            "[orchestrator] ── Rendering scene %d/%d (type: %s, hint: %.0fs)",
            idx + 1, total_scenes, scene.manim_scene_type,
            scene.duration_hint_seconds,
        )

        clip_path = None
        last_error = ""
        original_code = scene.manim_code  # preserve original for LLM repair context

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

                if not scene.manim_code:
                    # No code to fix — shouldn't happen but bail
                    break

                if attempt == 1:
                    # First failure: try sanitizing LaTeX → Text
                    is_latex_error = any(
                        kw in err_lower
                        for kw in ("dvi", "svg", "latex", "cache", "tex(")
                    )
                    if is_latex_error:
                        sanitized = self._sanitize_latex_to_text(scene.manim_code)
                        if sanitized != scene.manim_code:
                            scene.manim_code = sanitized
                            logger.warning(
                                "[orchestrator] Scene %d: sanitized Tex→Text, retrying",
                                idx + 1,
                            )
                        else:
                            # Sanitization didn't change anything — go straight to LLM fix
                            fixed = self._fix_code_with_llm(
                                scene.manim_code, last_error, idx + 1,
                            )
                            if fixed:
                                scene.manim_code = fixed
                    else:
                        # Non-LaTeX error — ask Claude to fix the code
                        fixed = self._fix_code_with_llm(
                            scene.manim_code, last_error, idx + 1,
                        )
                        if fixed:
                            scene.manim_code = fixed
                elif attempt == 2:
                    # Second failure — ask Claude to fix (using error from this attempt)
                    fixed = self._fix_code_with_llm(
                        scene.manim_code, last_error, idx + 1,
                    )
                    if fixed:
                        scene.manim_code = fixed
                # attempt 3+ just retries with whatever code we have

                if attempt < MAX_RENDER_RETRIES:
                    logger.info("[orchestrator] Retrying scene %d (attempt %d)...",
                                idx + 1, attempt + 1)

        if clip_path:
            elapsed = time.perf_counter() - scene_t0
            clip_size = Path(clip_path).stat().st_size / (1024 * 1024)
            logger.info(
                "[orchestrator] ✓ Scene %d OK: %s (%.1f MB, %.1fs)",
                idx + 1, clip_path, clip_size, elapsed,
            )
            return clip_path
        else:
            elapsed = time.perf_counter() - scene_t0
            logger.error(
                "[orchestrator] ✗ Scene %d FAILED after %d attempts (%.1fs): %s",
                idx + 1, MAX_RENDER_RETRIES, elapsed, last_error[:200],
            )
            raise RuntimeError(
                f"Scene {idx + 1} failed after {MAX_RENDER_RETRIES} attempts: {last_error[:200]}"
            )

    def _synthesize_one_voice(
        self,
        scene: SceneInstruction,
        character_id: str,
        tmp: Path,
        idx: int,
        voice_id: Optional[str],
        total_scenes: int,
    ) -> str:
        """Synthesize voice for a single scene. Returns audio file path."""
        voice_t0 = time.perf_counter()
        audio_path = str(tmp / f"voice_{idx:03d}.wav")
        logger.info(
            "[orchestrator] Synthesizing voice %d/%d: %d chars",
            idx + 1, total_scenes, len(scene.narration_text),
        )
        try:
            self._voice_synth.synthesize(
                text=scene.narration_text,
                character_id=character_id,
                output_path=audio_path,
                voice_id=voice_id,
            )
            audio_size = Path(audio_path).stat().st_size / 1024
            elapsed = time.perf_counter() - voice_t0
            logger.info(
                "[orchestrator] ✓ Voice %d OK: %.1f KB, %.1fs",
                idx + 1, audio_size, elapsed,
            )
            return audio_path
        except Exception as e:
            logger.error("[orchestrator] ✗ Voice %d FAILED: %s", idx + 1, e)
            logger.error("[orchestrator]   Traceback:\n%s", traceback.format_exc())
            raise

    # ------------------------------------------------------------------ #
    # Stage 3: Compositing (parallel)
    # ------------------------------------------------------------------ #

    def _run_compositing(
        self,
        rendered: list[tuple[SceneInstruction, str]],
        audio_clips: list[str],
        character_id: str,
        tmp: Path,
    ) -> list[str]:
        """Composite all scenes in parallel. Returns ordered list of clip paths."""
        total = len(rendered)
        results: dict[int, str] = {}
        progress_lock = threading.Lock()
        completed = [0]

        # Per-character sprite scale overrides (default 0.20)
        _SPRITE_SCALES = {
            "goku": 0.30,
            "peter": 0.22,
        }
        sprite_scale = _SPRITE_SCALES.get(character_id, 0.20)

        def _composite_one(idx: int) -> tuple[int, str]:
            scene, anim_clip = rendered[idx]
            comp_t0 = time.perf_counter()
            sprite_path = get_sprite_path(character_id, scene.character_action)
            composited_path = str(tmp / f"composited_{idx:03d}.mp4")
            logger.info("[orchestrator] Compositing scene %d/%d", idx + 1, total)
            self._compositor.composite(
                animation_clip=anim_clip,
                character_sprite=sprite_path,
                audio_file=audio_clips[idx],
                output_path=composited_path,
                scale=sprite_scale,
            )
            comp_size = Path(composited_path).stat().st_size / (1024 * 1024)
            elapsed = time.perf_counter() - comp_t0
            logger.info(
                "[orchestrator] ✓ Composite %d OK: %.1f MB, %.1fs",
                idx + 1, comp_size, elapsed,
            )
            return idx, composited_path

        with ThreadPoolExecutor(max_workers=MAX_COMPOSITE_WORKERS) as pool:
            futures = {pool.submit(_composite_one, idx): idx for idx in range(total)}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    scene_idx, path = future.result()
                    results[scene_idx] = path
                except Exception as e:
                    logger.error("[orchestrator] ✗ Composite %d FAILED: %s", idx + 1, e)
                    logger.error("[orchestrator]   Traceback:\n%s", traceback.format_exc())
                    raise
                with progress_lock:
                    completed[0] += 1
                    pct = 60 + int((completed[0] / total) * 20)
                    self._on_progress(JobStatus.COMPOSITING, pct)

        # Return in scene order
        return [results[i] for i in range(total)]

    # ------------------------------------------------------------------ #
    # Scene rendering helpers
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # LLM code repair (replaces static template fallback)
    # ------------------------------------------------------------------ #

    def _fix_code_with_llm(
        self, broken_code: str, error_message: str, scene_num: int,
    ) -> Optional[str]:
        """Ask Claude to fix broken ManimCE code based on the error.

        Returns the fixed code string, or None if the API call fails.
        """
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("[orchestrator] No ANTHROPIC_API_KEY — cannot call LLM for code fix")
            return None

        logger.info(
            "[orchestrator] Asking LLM to fix scene %d code (%d chars, error: %.120s...)",
            scene_num, len(broken_code), error_message,
        )

        system_prompt = (
            "You are a ManimCE (Community Edition) code repair expert.\n"
            "You will receive broken ManimCE Python code and the error it produced.\n"
            "Fix the code so it renders successfully.\n\n"
            "CRITICAL RULES:\n"
            "- Use ONLY `from manim import *` — never manimlib or manimgl.\n"
            "- The scene class MUST be named exactly `GeneratedScene` and extend `Scene`.\n"
            "- The `construct(self)` method must contain all animation logic.\n"
            "- NEVER use `MathTex(...)`, `Tex(...)`, or any LaTeX-based text.\n"
            "  ALWAYS use `Text(...)` for ALL text rendering. LaTeX is NOT available.\n"
            "  For math expressions, use Unicode: x², x₁, √, π, Σ, ∫, →, etc.\n"
            "- All text objects MUST have `font_size=36` or smaller.\n"
            "- After creating any text: `text.set_width(min(text.width, 10.0))`\n"
            "- Use `Create()` instead of `ShowCreation()`.\n"
            "- Use `axes = Axes(...)` not `axes = ThreeDAxes(...)` unless 3D is needed.\n"
            "- End every scene with `self.wait(1)`.\n"
            "- Do NOT use `TransformMatchingTex` — use `ReplacementTransform` instead.\n"
            "- Do NOT use `VMobject.set_stroke_width()` with 0 args.\n"
            "- FadeOut everything at the end before self.wait: "
            "`self.play(*[FadeOut(m) for m in self.mobjects])`\n"
            "- Keep it simple: avoid complex layouts, 3D cameras, or advanced features.\n"
            "- Do NOT import any manim plugins (from manim_* import ...).\n"
            "- For axis labels: pass Text() objects, NOT strings. Strings trigger hidden LaTeX.\n"
            "  WRONG: axes.get_x_axis_label('x')\n"
            "  RIGHT: axes.get_x_axis_label(Text('x', font_size=28))\n"
            "- For graph labels: use Text().next_to() instead of get_graph_label() with strings.\n"
            "  WRONG: axes.get_graph_label(graph, 'f(x)')\n"
            "  RIGHT: Text('f(x)', font_size=28).next_to(axes.c2p(2, 4), RIGHT)\n"
            "- NEVER pass bare strings to get_graph_label(), get_T_label(), or any axes method.\n"
            "  These methods internally create MathTex which crashes without LaTeX.\n"
            "- The code must be COMPLETE and SELF-CONTAINED.\n\n"
            "Return ONLY the fixed Python code — no markdown fences, no explanation, "
            "no ```python blocks. Just raw Python code starting with `from manim import *`."
        )

        user_message = (
            f"This ManimCE code for scene {scene_num} failed to render.\n\n"
            f"ERROR:\n{error_message[:1500]}\n\n"
            f"BROKEN CODE:\n{broken_code}"
        )

        try:
            client = anthropic.Anthropic(api_key=api_key)
            t0 = time.perf_counter()
            response = client.messages.create(
                model=_CODE_FIX_MODEL,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            elapsed = time.perf_counter() - t0

            fixed_code = response.content[0].text.strip()

            # Strip markdown fences if the model included them anyway
            if fixed_code.startswith("```"):
                lines = fixed_code.split("\n")
                # Remove first line (```python) and last line (```)
                if lines[-1].strip() == "```":
                    lines = lines[1:-1]
                else:
                    lines = lines[1:]
                fixed_code = "\n".join(lines).strip()

            # Basic sanity checks
            if "from manim import" not in fixed_code:
                logger.warning("[orchestrator] LLM fix missing 'from manim import' — discarding")
                return None
            if "class GeneratedScene" not in fixed_code:
                logger.warning("[orchestrator] LLM fix missing 'class GeneratedScene' — discarding")
                return None
            if "def construct" not in fixed_code:
                logger.warning("[orchestrator] LLM fix missing 'def construct' — discarding")
                return None

            logger.info(
                "[orchestrator] LLM fix for scene %d: %d chars (%.1fs, model=%s)",
                scene_num, len(fixed_code), elapsed, _CODE_FIX_MODEL,
            )
            return fixed_code

        except Exception as exc:
            logger.error(
                "[orchestrator] LLM code fix failed for scene %d: %s", scene_num, exc,
            )
            return None
