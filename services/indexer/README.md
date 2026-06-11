# Indexer Service

One-shot ingestion service. Connects to Typesense and Qdrant, round-trips a
dummy document in each, and exits. Used to verify both search backends are
reachable and writable.

## Run (via compose)

```bash
docker compose run --rm indexer
```

## Run locally (dev)

```bash
cd services/indexer
uv sync
TYPESENSE_HOST=localhost TYPESENSE_PORT=8108 TYPESENSE_API_KEY=local-dev-key \
QDRANT_HOST=localhost QDRANT_PORT=6333 \
uv run python main.py
```

## Expected output

```
[INFO] Indexer starting
[INFO] Typesense: created collection ...
[INFO] Typesense: wrote document
[INFO] Typesense: read back document ...
[INFO] Typesense: cleaned up collection
[INFO] Typesense: OK
[INFO] Qdrant: created collection ...
[INFO] Qdrant: wrote point
[INFO] Qdrant: read back point ...
[INFO] Qdrant: cleaned up collection
[INFO] Qdrant: OK
[INFO] Indexer finished successfully
```
