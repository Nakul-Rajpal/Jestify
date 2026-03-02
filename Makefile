.PHONY: dev dev-frontend dev-backend dev-worker setup-frontend setup-backend setup-pipeline docker-up docker-down

PYTHON ?= $(if $(VIRTUAL_ENV),$(VIRTUAL_ENV)/bin/python,python3)

# Start all services via Docker
docker-up:
	docker compose up -d

docker-down:
	docker compose down

# Local development (run each in separate terminals)
dev-frontend:
	cd frontend && npm run dev

dev-backend:
	cd backend && $(PYTHON) -m uvicorn app.main:app --reload --port 8000

dev-worker:
	$(eval TEXMF_WEB2C := $(shell kpsewhich texmf.cnf 2>/dev/null | xargs dirname 2>/dev/null))
	export TEXMFCNF="$(TEXMF_WEB2C):"; \
	export TEXMFDIST="$(shell dirname $(TEXMF_WEB2C) 2>/dev/null)"; \
	PYTHONPATH=pipeline:. $(PYTHON) -m celery -A pipeline.worker worker -Q video_pipeline -c 1 --loglevel=info

# Setup
setup-frontend:
	cd frontend && npm install

setup-backend:
	cd backend && $(PYTHON) -m pip install -r requirements.txt

setup-pipeline:
	cd pipeline && $(PYTHON) -m pip install -r requirements.txt

setup: setup-frontend setup-backend setup-pipeline

# Database
db-migrate:
	cd backend && alembic upgrade head

db-revision:
	cd backend && alembic revision --autogenerate -m "$(msg)"
