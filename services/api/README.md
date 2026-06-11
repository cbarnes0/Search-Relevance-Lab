# API Service

FastAPI backend. Exposes `/health` reporting connectivity to postgres, typesense, and qdrant.

## Run (via compose)

```bash
docker compose up api
```

## Run locally (dev)

```bash
cd services/api
uv sync
uv run uvicorn main:app --reload
```

## Verify

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status":"healthy","backends":{"postgres":true,"typesense":true,"qdrant":true}}
```
