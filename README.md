# Search Relevance Lab

A multi-backend search evaluation platform comparing lexical (Typesense), vector (Qdrant), and hybrid retrieval across a real corpus, with retrieval-quality metrics (nDCG, MRR, recall@k) computed against stored relevance judgments.

## Services

| Service    | Description                              | Port  |
|------------|------------------------------------------|-------|
| `postgres`  | Metadata, queries, judgments, eval runs | 5432  |
| `typesense` | Lexical search backend                  | 8108  |
| `qdrant`    | Vector search backend                   | 6333  |
| `api`       | FastAPI — health, eval orchestration    | 8000  |
| `web`       | Next.js — dashboard UI                  | 3000  |
| `indexer`   | One-shot corpus ingestion service        | —     |

## Quick Start

```bash
cp .env.example .env
docker compose up
```

See [apps/web/README.md](apps/web/README.md), [services/api/README.md](services/api/README.md), and [services/indexer/README.md](services/indexer/README.md) for per-service instructions.

## Phase Roadmap

- **Phase 1** — Docker dev environment, service skeletons, health checks ✅
- **Phase 2** — Corpus ingestion, embeddings, real index population
- **Phase 3** — Eval metrics (nDCG, MRR, recall@k), judgment storage
- **Phase 4** — Hybrid fusion, Terraform, ECS deployment
