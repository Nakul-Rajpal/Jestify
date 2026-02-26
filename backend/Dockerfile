# Build context: project root (needed for shared/ package imports)
# Railway service config file: backend/railway.toml

FROM python:3.11-slim

# System deps for pymupdf, pytesseract, asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libglib2.0-0 \
    libgl1 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy shared package (imported by backend/app/main.py via sys.path)
COPY shared/ ./shared/

# Install backend dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source
COPY backend/ ./backend/

# WORKDIR inside backend so uvicorn resolves 'app.main:app' correctly
WORKDIR /app/backend

# PYTHONPATH=/app makes 'shared' importable (sys.path insert in main.py also does this)
ENV PYTHONPATH=/app
ENV STORAGE_PATH=/app/storage
# Force unbuffered output so logs are visible in Railway
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
