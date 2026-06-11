.PHONY: up down build restart logs ps health index lint-api

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

index:
	docker compose run --rm indexer

lint-api:
	docker compose exec api ruff check .
