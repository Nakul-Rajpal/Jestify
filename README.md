# Jestify

Turn educational materials into engaging STEM lecture videos narrated by your favorite characters.

Upload your homework, notes, or lecture slides — pick a character like SpongeBob or Superman — and Jestify generates a 3Blue1Brown-quality animated video where that character teaches the concepts using their personality and universe.

## Architecture

```
frontend/     →  Next.js (TypeScript, Tailwind) — ChatGPT-style UI
backend/      →  FastAPI (Python) — Document processing, LLM script generation, job orchestration
pipeline/     →  Python — ManimGL rendering, voice synthesis, video assembly
shared/       →  Shared contracts (Python + TypeScript types)
```

Each top-level directory is owned by one collaborator. Communication happens through REST API (frontend ↔ backend) and Celery/Redis job queue (backend → pipeline).

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Docker & Docker Compose
- FFmpeg

### 1. Start infrastructure
```bash
docker compose up -d postgres redis
```

### 2. Set up environment
```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
```

### 3. Install dependencies
```bash
make setup
```

### 4. Run database migrations
```bash
make db-migrate
```

### 5. Start services (each in a separate terminal)

**Frontend:**
```bash
make dev-frontend   # http://localhost:3000
```

**Backend:**
```bash
make dev-backend    # http://localhost:8000
```

**Pipeline worker** (from the `pipeline/` directory):
```bash
cd pipeline
eval "$(/usr/libexec/path_helper)"
PYTHONPATH=.:.. celery -A pipeline.worker worker -Q video_pipeline -c 1 --loglevel=info
```

### Or use Docker for everything
```bash
docker compose up
```

## How It Works

1. **Select** a character and difficulty level
2. **Upload** educational documents (PDF, images, text)
3. **Submit** — the system:
   - Extracts text from documents
   - Uses Claude to generate a structured script in the character's voice
   - Renders ManimGL animations for each scene
   - Synthesizes character voice audio (Qwen3-TTS)
   - Composites character overlay onto animations
   - Assembles the final video
4. **Watch** the generated lecture video

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy, Alembic |
| Job Queue | Celery + Redis |
| Database | PostgreSQL |
| LLM | Claude (Anthropic API) |
| Animations | ManimGL (3Blue1Brown) |
| Voice | Qwen3-TTS |
| Video | FFmpeg |

## Project Structure

```
Jestify/
├── frontend/          # Collaborator 1 — UI
├── backend/           # Collaborator 2 — API & orchestration
├── pipeline/          # Collaborator 3 — Video generation
├── shared/            # Shared type contracts
├── docker-compose.yml
├── Makefile
└── .env.example
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/characters | List available characters |
| POST | /api/documents/upload | Upload educational material |
| POST | /api/generate | Start video generation |
| GET | /api/jobs/{id} | Poll job progress |
| GET | /api/jobs/{id}/video | Get completed video |
