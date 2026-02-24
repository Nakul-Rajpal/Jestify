# ── Pipeline Worker: Celery + ManimCE + FFmpeg + TeX Live ────────────────── #
# Build context MUST be the project root so shared/ and backend/ are accessible.
#   docker build -f pipeline/Dockerfile .
# ────────────────────────────────────────────────────────────────────────── #

FROM python:3.13-slim AS base

# ── System dependencies ────────────────────────────────────────────────── #
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Manim runtime
    ffmpeg \
    # TeX Live for MathTex / LaTeX rendering (dvisvgm, latex, etc.)
    texlive-full \
    # Cairo/Pango for Text() rendering in Manim
    libcairo2-dev \
    libpango1.0-dev \
    pkg-config \
    # Build tools for native Python extensions
    gcc \
    g++ \
    # Misc
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── TeX environment (must be set before Celery forks) ──────────────────── #
ENV TEXMFCNF=/usr/share/texmf/web2c:
ENV TEXMFDIST=/usr/share/texmf

# ── Python dependencies ───────────────────────────────────────────────── #
WORKDIR /app

# Install both pipeline and backend requirements (layer cache).
# The worker imports backend.app.services.script_generator at runtime.
COPY pipeline/requirements.txt /app/pipeline-requirements.txt
COPY backend/requirements.txt /app/backend-requirements.txt
RUN pip install --no-cache-dir \
    -r /app/pipeline-requirements.txt \
    -r /app/backend-requirements.txt

# ── Application code ──────────────────────────────────────────────────── #
# shared/ — contracts imported by both backend and pipeline
COPY shared/ /app/shared/

# pipeline/ — worker, orchestrator, renderers, voice synth, compositor
COPY pipeline/pipeline/ /app/pipeline/pipeline/
COPY pipeline/assets/ /app/pipeline/assets/

# backend/ — the worker imports backend.app.services.script_generator
COPY backend/__init__.py /app/backend/__init__.py
COPY backend/app/ /app/backend/app/

# ── Storage directory ─────────────────────────────────────────────────── #
RUN mkdir -p /app/storage

# ── Runtime ───────────────────────────────────────────────────────────── #
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV STORAGE_PATH=/app/storage
ENV ASSETS_PATH=/app/pipeline/assets

# Celery worker: single process (Manim rendering is CPU-bound)
CMD ["celery", "-A", "pipeline.pipeline.worker", "worker", \
     "-Q", "video_pipeline", "-c", "1", "--loglevel=info"]
