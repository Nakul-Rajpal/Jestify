"""Temporary file and directory management for pipeline jobs."""

import logging
import shutil
import tempfile
from pathlib import Path

from pipeline.config import STORAGE_PATH

logger = logging.getLogger(__name__)

_TEMP_BASE = Path(STORAGE_PATH) / "tmp"


def create_job_temp_dir(job_id: str) -> str:
    """Create and return a temporary directory for a specific job.

    Parameters
    ----------
    job_id : str
        Unique job identifier.

    Returns
    -------
    str
        Absolute path to the created temporary directory.
    """
    _TEMP_BASE.mkdir(parents=True, exist_ok=True)
    job_dir = _TEMP_BASE / f"job_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Created job temp dir: %s", job_dir)
    return str(job_dir)


def cleanup_job_temp_dir(job_id: str) -> None:
    """Remove the temporary directory for a job.

    Parameters
    ----------
    job_id : str
        Unique job identifier.
    """
    job_dir = _TEMP_BASE / f"job_{job_id}"
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
        logger.debug("Cleaned up job temp dir: %s", job_dir)
    else:
        logger.debug("Job temp dir does not exist (already cleaned?): %s", job_dir)


def cleanup_all_temp() -> None:
    """Remove all temporary pipeline files.

    Use with caution -- this deletes **all** job temp directories.
    """
    if _TEMP_BASE.exists():
        shutil.rmtree(_TEMP_BASE, ignore_errors=True)
        logger.info("Cleaned up all pipeline temp files at %s", _TEMP_BASE)
