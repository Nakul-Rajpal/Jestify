"""Router for serving the example video (for preview/demo)."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import settings

router = APIRouter(tags=["example"])


@router.get("/example-video")
async def get_example_video() -> FileResponse:
    """
    Return the 1-minute example video if it exists.
    Generate it first by running: ./scripts/generate_example_video.sh
    """
    video_path = Path(settings.STORAGE_PATH) / "example" / "example-video.mp4"
    if not video_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Example video not found. Run: ./scripts/generate_example_video.sh",
        )
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename="jestify-example-video.mp4",
    )
