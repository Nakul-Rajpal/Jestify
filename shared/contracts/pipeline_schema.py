from pydantic import BaseModel
from typing import List, Optional

from .enums import Character, Difficulty


class SceneInstruction(BaseModel):
    """A single scene in the generated script."""

    scene_index: int
    narration_text: str
    manim_scene_type: str = "custom"
    manim_parameters: dict = {}
    duration_hint_seconds: float = 60.0
    character_action: str = "talking"
    manim_code: Optional[str] = None


class GeneratedScript(BaseModel):
    """Full script output from the LLM."""

    title: str
    character: Character
    difficulty: Difficulty
    total_scenes: int
    scenes: List[SceneInstruction]
    intro_text: str
    outro_text: str
    language: str = "en"


class PipelineInput(BaseModel):
    """What the backend sends to the pipeline via Celery."""

    job_id: str
    script: GeneratedScript
    character: Character
    output_path: str
    voice_id: Optional[str] = None


class PipelineOutput(BaseModel):
    """What the pipeline returns on completion."""

    job_id: str
    video_path: str
    duration_seconds: float
    thumbnail_path: Optional[str] = None
    error: Optional[str] = None
