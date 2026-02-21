.PHONY: dev dev-frontend dev-backend dev-worker setup-frontend setup-backend setup-pipeline docker-up docker-down

# Start all services via Docker
docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Local development (run each in separate terminals)
dev-frontend:
	cd frontend && npm run dev

dev-backend:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-worker:
	PYTHONPATH=pipeline:. celery -A pipeline.worker worker -Q video_pipeline -c 1 --loglevel=info

# Setup
setup-frontend:
	cd frontend && npm install

setup-backend:
	cd backend && pip install -r requirements.txt

setup-pipeline:
	cd pipeline && pip install -r requirements.txt

setup: setup-frontend setup-backend setup-pipeline

# Database
db-migrate:
	cd backend && alembic upgrade head

db-revision:
	cd backend && alembic revision --autogenerate -m "$(msg)"
