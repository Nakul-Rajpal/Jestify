"""
Pydantic schemas for generation-related requests and responses.

Re-exports from shared contracts for convenience, plus any backend-specific schemas.
"""

# Re-export shared contract types so routers can import from one place
from shared.contracts.api_types import (  # noqa: F401
    GenerateRequest,
    GenerateResponse,
    JobStatusResponse,
    DocumentUploadResponse,
    CharacterInfo,
    CharacterListResponse,
    VoiceInfo,
    VoiceListResponse,
)
from shared.contracts.pipeline_schema import (  # noqa: F401
    SceneInstruction,
    GeneratedScript,
    PipelineInput,
    PipelineOutput,
)
from shared.contracts.enums import (  # noqa: F401
    Character,
    Difficulty,
    JobStatus,
    DocumentType,
)
