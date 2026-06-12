# API Service

FastAPI backend. Exposes `/health` (backend connectivity) and `/search` (lexical
or vector retrieval with a normalized response shape).

## Endpoints

### `GET /search?q=<text>&backend=lexical|vector&k=10`

Returns the same shape regardless of backend — this normalization is what makes
Phase 4 fusion possible:

```json
{
  "query": "heart attack",
  "backend": "vector",
  "k": 10,
  "latency_ms": 52.3,
  "results": [
    { "doc_id": "MED-4891", "title": "...", "snippet": "...", "score": 0.7436, "rank": 1 }
  ]
}
```

- `lexical` → Typesense (`query_by=title,text`, title weighted 2:1).
- `vector` → embed the query (`bge-small-en-v1.5`, with retrieval prefix), then
  search Qdrant. The model loads once at startup and is warmed; `encode()` runs
  in a thread so it never blocks the event loop.
- `score` is **not** comparable across backends (lexical = large `text_match`
  int; vector = cosine 0..1). Use `rank` for cross-backend comparison.

### `GET /health`

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
