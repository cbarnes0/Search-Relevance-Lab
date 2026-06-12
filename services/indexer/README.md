# Indexer Service

One-shot tool service. Loads the NFCorpus corpus into Postgres and builds the
lexical (Typesense) and vector (Qdrant) search indexes. Runs under the `tools`
compose profile (not part of `docker compose up`).

All scripts are **idempotent** — safe to re-run; they upsert rather than
duplicate.

## Scripts

| Script | Action |
|---|---|
| `ingest.py` | Load documents, queries, qrels into Postgres (`schema.sql`). Pydantic-validated, batch-upserted. |
| `index_lexical.py` | Read documents from Postgres, (re)build the Typesense `documents` collection. |
| `index_vector.py` | Read documents, embed with `bge-small-en-v1.5`, upsert vectors into Qdrant. |
| `query_vector.py "<q>"` | Quick semantic-search check against Qdrant. |
| `main.py` | Phase 1 backend connectivity smoke test. |

## Run (via compose / make)

```bash
make ingest          # docker compose run --rm indexer python ingest.py
make index-lexical
make index-vector
make index           # all three in order

# semantic search check
docker compose run --rm indexer python query_vector.py "heart attack"
```

## Data sources

The dataset and model are downloaded on the **host** (the container network is
locked down) and bind-mounted in:

- `IR_DATASETS_HOME=/data/ir_datasets` ← `./data/ir_datasets` (NFCorpus cache)
- `HF_HOME=/data/hf_cache` ← `./data/hf_cache` (model weights; `HF_HUB_OFFLINE=1`)

See `scripts/host_check.py` and `scripts/host_download_model.py` in the repo root.

## Schema

`schema.sql` defines `documents`, `queries`, `qrels`. Natural keys (dataset
doc/query IDs); `qrels.doc_id` is FK-constrained to `documents`; `relevance` is
graded `SMALLINT` (0/1/2). See the file for the full rationale.

## Notes

- Embedding model/dims come from `EMBEDDING_MODEL` / `EMBEDDING_DIM` (env).
- `qdrant-client` is pinned `<1.10` to match the Qdrant server (`v1.9.4`).
- Documents are embedded without an instruction prefix; queries use the bge
  retrieval prefix (see `query_vector.py`).
