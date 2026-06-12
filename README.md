# Search Relevance Lab

A multi-backend search evaluation platform comparing lexical (Typesense), vector (Qdrant), and hybrid retrieval across a real corpus, with retrieval-quality metrics (nDCG, MRR, recall@k) computed against stored relevance judgments.

**Status:** Phase 2 — end-to-end lexical + vector search with a side-by-side comparison UI. (Phase 3 adds evaluation metrics; Phase 4 adds hybrid fusion.)

![Side-by-side lexical vs. vector results for the query "heart attack"](docs/comparison-ui.png)

The comparison UI for `heart attack`: lexical (Typesense) matches the literal
tokens, while vector (Qdrant) returns the semantic cluster — sudden cardiac
death, angina — that shares few of the query's words. With the model warm, the
two backends have comparable latency (~44ms vs. ~55ms).

## Services

| Service     | Description                                          | Port |
|-------------|------------------------------------------------------|------|
| `postgres`  | System of record: documents, queries, qrels          | 5432 |
| `typesense` | Lexical search backend                               | 8108 |
| `qdrant`    | Vector search backend                                | 6333 |
| `api`       | FastAPI — `/health`, `/search` (lexical \| vector)    | 8000 |
| `web`       | Next.js — side-by-side comparison UI                 | 3000 |
| `indexer`   | One-shot tool: ingest corpus, build both indexes     | —    |

## Corpus

[BEIR / NFCorpus](https://ir-datasets.com/beir.html#beir/nfcorpus) — a medical IR benchmark (PubMed abstracts, layman questions from NutritionFacts.org). We load the **test** split:

| | Count |
|---|---|
| Documents | 3,633 |
| Queries | 323 |
| Relevance judgments (qrels) | 12,334 |

Qrels are **graded** (0 / 1 / 2), which Phase 3's nDCG depends on.

## Architecture

```
host (one-time):  ir_datasets ──► ./data/ir_datasets   (NFCorpus cache)
                  bge-small   ──► ./data/hf_cache       (model weights)
                       │ bind-mounted into containers
                       ▼
indexer  ingest.py        ──► Postgres   (documents, queries, qrels)
         index_lexical.py ──► Postgres ─► Typesense   (title, text searchable)
         index_vector.py  ──► Postgres ─► encode ─► Qdrant   (384-dim, cosine)

api  GET /search?q=&backend=lexical|vector&k=10
        lexical: Typesense query
        vector:  embed query ─► Qdrant search
        ─► normalized response { doc_id, title, snippet, score, rank } + latency_ms

web  server-fetches BOTH backends ─► renders two columns side by side
```

The embedding model and dimensions are configured via `EMBEDDING_MODEL` / `EMBEDDING_DIM` (env), not hardcoded — they can be swapped without code changes.

## Quick start

### 1. Host prerequisites (one-time)

The container network is locked down, so the dataset and model are downloaded on the host into `./data/` (bind-mounted into the containers).

```bash
cp .env.example .env

python -m venv .venv-host
# Windows:  .venv-host\Scripts\Activate.ps1
# Unix:     source .venv-host/bin/activate
pip install ir-datasets sentence-transformers

python scripts/host_check.py           # NFCorpus  -> ./data/ir_datasets
python scripts/host_download_model.py   # bge-small -> ./data/hf_cache
```

### 2. Bring up infrastructure and build indexes

```bash
docker compose up -d postgres typesense qdrant
docker compose build
make index          # ingest -> index-lexical -> index-vector
```

### 3. Start the app

```bash
docker compose up -d api web
```

Open <http://localhost:3000> and search (try `heart attack` to see lexical token-matching vs. vector semantic retrieval).

## Integration checklist (fresh slate)

Verifies the whole pipeline from empty volumes. Note: `down -v` wipes the database **volumes** but not `./data/` (host dirs), so the dataset/model are not re-downloaded.

1. `docker compose down -v` — remove containers **and** named volumes.
2. `docker compose up -d postgres typesense qdrant` — wait for healthy.
3. `docker compose build`
4. `make ingest` — expect `3633 docs, 323 queries, 12334 qrels`.
5. `make index-lexical` — expect `Typesense reports 3633 documents`.
6. `make index-vector` — expect `Qdrant reports 3633 points`.
7. `docker compose up -d api web`
8. `curl "http://localhost:8000/search?q=heart%20attack&backend=vector&k=5"` — normalized results.
9. Open <http://localhost:3000>, search, confirm both columns render.

## Make targets

| Target | Action |
|---|---|
| `make up` / `make down` | start / stop the stack |
| `make index` | ingest + build both search indexes |
| `make ingest` / `make index-lexical` / `make index-vector` | individual pipeline steps |
| `make health` | print API health JSON |
| `make logs` / `make ps` | tail logs / list containers |
