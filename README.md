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
