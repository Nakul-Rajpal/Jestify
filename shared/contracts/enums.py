from enum import Enum


class Character(str, Enum):
    LEBRON = "lebron"
    GOKU = "goku"
    PETER = "peter"
    ALYSA = "alysa"


class Difficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class JobStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING_TEXT = "extracting_text"
    GENERATING_SCRIPT = "generating_script"
    GENERATING_ANIMATIONS = "generating_animations"
    RENDERING_ANIMATIONS = "rendering_animations"
    SYNTHESIZING_VOICE = "synthesizing_voice"
    COMPOSITING = "compositing"
    ASSEMBLING = "assembling"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, Enum):
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    URL = "url"
