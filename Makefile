.DEFAULT_GOAL := help
.PHONY: help setup install services down migrate seed ingest backend frontend dev tunnel \
	elevenlabs-agent chat test lint docker docker-init

BACKEND := cd backend &&
FRONTEND := cd frontend &&

help: ## Show this help
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: install services migrate seed ingest ## First-time setup: deps, datastores, schema, demo data, knowledge base

install: ## Install backend (uv) and frontend (npm) dependencies
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	$(BACKEND) uv sync
	$(FRONTEND) npm install

services: ## Start Postgres and Qdrant in Docker
	docker compose up -d --wait postgres qdrant

down: ## Stop all containers
	docker compose --profile app down

migrate: ## Apply database migrations
	$(BACKEND) uv run alembic upgrade head

seed: ## Load the mock Lauki plans, customers, bills and usage
	$(BACKEND) uv run python -m app.db.seed

ingest: ## Chunk, embed and index the PDFs in data/knowledge
	$(BACKEND) uv run python -m app.rag.ingest

backend: ## Run the FastAPI backend with reload on :8000
	$(BACKEND) uv run uvicorn app.main:app --reload --port 8000

frontend: ## Run the Next.js dashboard on :3000
	$(FRONTEND) npm run dev

dev: ## Run backend and frontend together (Ctrl+C stops both)
	@trap 'kill 0' INT TERM; $(MAKE) backend & $(MAKE) frontend & wait

tunnel: ## Expose the backend over HTTPS with ngrok (set PUBLIC_BACKEND_URL to the URL it prints)
	ngrok http 8000

elevenlabs-agent: ## Create/update the ElevenLabs agent (ARGS=--twilio to also import the Twilio number)
	$(BACKEND) uv run python -m scripts.setup_elevenlabs_agent $(ARGS)

chat: ## Text chat with the agent in the terminal (ARGS="--caller +919876543210" to simulate caller ID)
	$(BACKEND) uv run python -m scripts.chat $(ARGS)

test: ## Run the backend test suite (needs `make services`)
	$(BACKEND) uv run pytest -q

lint: ## Lint backend and frontend
	$(BACKEND) uv run ruff check . && uv run ruff format --check .
	$(FRONTEND) npx tsc --noEmit && npm run lint

docker: ## Run the whole stack in Docker (backend :8000, dashboard :3000)
	docker compose --profile app up --build

docker-init: ## Seed demo data and index the knowledge base inside the running Docker stack
	docker compose exec backend python -m app.db.seed
	docker compose exec backend python -m app.rag.ingest
