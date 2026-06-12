.PHONY: up down build restart logs ps health ingest index-lexical index-vector index smoke lint-api

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

restart:
	docker compose down && docker compose up -d

logs:
	docker compose logs -f

ps:
	docker compose ps

health:
	docker compose exec api python -c "import urllib.request, json; print(json.dumps(json.load(urllib.request.urlopen('http://localhost:8000/health')), indent=2))"

# --- Phase 2: corpus ingestion + indexing (indexer is a one-shot tool) ---
ingest:
	docker compose run --rm indexer python ingest.py

index-lexical:
	docker compose run --rm indexer python index_lexical.py

index-vector:
	docker compose run --rm indexer python index_vector.py

# Full pipeline: load Postgres, then build both search indexes.
index: ingest index-lexical index-vector

# Phase 1 backend connectivity smoke test.
smoke:
	docker compose run --rm indexer python main.py

lint-api:
	docker compose exec api ruff check .
