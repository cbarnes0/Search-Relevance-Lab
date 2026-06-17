import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

import asyncpg
import httpx
from fastapi import FastAPI, Query
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from fusion import reciprocal_rank_fusion, weighted_fusion

TYPESENSE_HOST = os.environ.get("TYPESENSE_HOST", "typesense")
TYPESENSE_PORT = os.environ.get("TYPESENSE_PORT", "8108")
TYPESENSE_API_KEY = os.environ.get("TYPESENSE_API_KEY", "")
QDRANT_HOST = os.environ.get("QDRANT_HOST", "qdrant")
QDRANT_PORT = os.environ.get("QDRANT_PORT", "6333")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

COLLECTION = "documents"
SNIPPET_LEN = 200
# Must match the prefix used when documents were indexed (query_vector.py).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once at startup (never per-request). to_thread keeps the
    # event loop free while the weights load.
    app.state.model = await asyncio.to_thread(SentenceTransformer, EMBEDDING_MODEL)
    # Warm up: the first encode triggers one-time torch init (~seconds). Pay it
    # here at boot so the first real query isn't penalized.
    await asyncio.to_thread(
        lambda: app.state.model.encode("warmup", normalize_embeddings=True)
    )
    # Connection pool for eval read-endpoints: open connections once at boot,
    # borrow per request via `async with app.state.pool.acquire() as conn`.
    app.state.pool = await asyncpg.create_pool(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        database=os.environ["POSTGRES_DB"],
        min_size=1,
        max_size=5,
    )
    yield
    await app.state.pool.close()


app = FastAPI(title="Search Relevance Lab API", lifespan=lifespan)


# --- Normalized response contract -----------------------------------------
class SearchResult(BaseModel):
    doc_id: str
    title: str
    snippet: str
    score: float
    rank: int


class SearchResponse(BaseModel):
    query: str
    backend: str
    k: int
    latency_ms: float
    results: list[SearchResult]


class RunSummary(BaseModel):
    id: int
    created_at: datetime
    backend: str
    dataset: str
    k: int
    embedding_model: str | None  # NULL for lexical
    git_sha: str
    concurrency: int
    n_queries: int
    mean_precision: float
    mean_recall: float
    mean_mrr: float
    mean_ndcg: float
    latency_p50_ms: float | None
    latency_p95_ms: float | None


class QueryComparison(BaseModel):
    query_id: str
    query_text: str
    a_precision: float
    a_recall: float
    a_mrr: float
    a_ndcg: float
    b_precision: float
    b_recall: float
    b_mrr: float
    b_ndcg: float


class RankedDoc(BaseModel):
    rank: int
    doc_id: str
    title: str
    relevance: int  # 0 = not relevant, >0 = relevant grade


class QueryDrilldown(BaseModel):
    query_id: str
    query_text: str
    a: list[RankedDoc]
    b: list[RankedDoc]


class FusionQueryRow(BaseModel):
    query_id: str
    query_text: str
    lexical_ndcg: float
    vector_ndcg: float
    hybrid_ndcg: float
    category: Literal["beat_both", "lost_both", "between", "tied"]


# --- Backends: identical output shape, different retrieval ------------------
async def run_lexical(client: httpx.AsyncClient, q: str, k: int) -> list[SearchResult]:
    resp = await client.get(
        f"http://{TYPESENSE_HOST}:{TYPESENSE_PORT}/collections/{COLLECTION}/documents/search",
        params={
            "q": q,
            "query_by": "title,text",
            "query_by_weights": "1,1",
            "per_page": k,
        },
        headers={"X-TYPESENSE-API-KEY": TYPESENSE_API_KEY},
        timeout=10.0,
    )
    resp.raise_for_status()
    hits = resp.json()["hits"]
    return [
        SearchResult(
            doc_id=hit["document"]["id"],
            title=hit["document"]["title"],
            snippet=hit["document"]["text"][:SNIPPET_LEN],
            score=float(hit["text_match"]),  # large int; not comparable to cosine
            rank=rank,
        )
        for rank, hit in enumerate(hits, 1)
    ]


async def run_vector(
    app: FastAPI, client: httpx.AsyncClient, q: str, k: int
) -> list[SearchResult]:
    # encode() is blocking CPU work — offload so the event loop stays responsive.
    vector = await asyncio.to_thread(
        lambda: app.state.model.encode(
            QUERY_PREFIX + q, normalize_embeddings=True
        ).tolist()
    )
    resp = await client.post(
        f"http://{QDRANT_HOST}:{QDRANT_PORT}/collections/{COLLECTION}/points/search",
        json={"vector": vector, "limit": k, "with_payload": True},
        timeout=10.0,
    )
    resp.raise_for_status()
    points = resp.json()["result"]
    return [
        SearchResult(
            doc_id=point["payload"]["doc_id"],
            title=point["payload"]["title"],
            snippet=point["payload"]["text"][:SNIPPET_LEN],
            score=point["score"],  # cosine, 0..1
            rank=rank,
        )
        for rank, point in enumerate(points, 1)
    ]


CANDIDATE_POOL = 100


async def run_hybrid(
    app: FastAPI,
    client: httpx.AsyncClient,
    q: str,
    k: int,
    fusion_method: Literal["rrf", "weighted"],
    rrf_k: int,
    alpha: float,
) -> list[SearchResult]:
    # 1. Retrieve both result sets concurrently
    lexical, vector = await asyncio.gather(
        run_lexical(client, q, CANDIDATE_POOL),
        run_vector(app, client, q, CANDIDATE_POOL),
    )

    # 2. Fuse -> list[tuple[doc_id, fused_score]]
    if fusion_method == "rrf":
        fused = reciprocal_rank_fusion(
            [[r.doc_id for r in lexical], [r.doc_id for r in vector]],
            k=rrf_k,
        )
    else:
        lexical_scores = {r.doc_id: r.score for r in lexical}
        vector_scores = {r.doc_id: r.score for r in vector}
        fused = weighted_fusion(
            lexical_scores,  # {doc_id: raw score} for lexical
            vector_scores,  # {doc_id: raw score} for vector
            alpha=alpha,
        )

    # 3. doc_id -> SearchResult lookup, merged from both pools.
    #    (a doc in both is identical; merge so docs unique to one survive)
    lookup: dict[str, SearchResult] = {r.doc_id: r for r in lexical}
    for r in vector:
        if r.doc_id not in lookup:
            lookup[r.doc_id] = r

    # 4. Rebuild the contract shape: top-k, fused score, fresh rank.
    results = []
    for rank, (doc_id, score) in enumerate(fused[:k], start=1):
        original = lookup[doc_id]
        results.append(
            SearchResult(
                doc_id=doc_id,
                title=original.title,  # from original
                snippet=original.snippet,  # from original
                score=score,  # FUSED score, not backend score
                rank=rank,
            )
        )
    return results


@app.get("/search")
async def search(
    q: str,
    backend: Literal["lexical", "vector", "hybrid"] = "lexical",
    k: int = Query(10, ge=1, le=100),
    fusion_method: Literal["rrf", "weighted"] = "rrf",
    rrf_k: int = Query(60, ge=0),
    alpha: float = Query(0.5, ge=0.0, le=1.0),
) -> SearchResponse:
    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        if backend == "lexical":
            results = await run_lexical(client, q, k)
        elif backend == "vector":
            results = await run_vector(app, client, q, k)
        else:
            results = await run_hybrid(app, client, q, k, fusion_method, rrf_k, alpha)
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    return SearchResponse(
        query=q, backend=backend, k=k, latency_ms=latency_ms, results=results
    )


# --- Config: lets the eval runner record what the API was actually using ----
@app.get("/config")
async def config() -> dict:
    return {"embedding_model": EMBEDDING_MODEL, "collection": COLLECTION}


# --- Health (unchanged) -----------------------------------------------------
async def check_postgres() -> bool:
    try:
        conn = await asyncpg.connect(
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            database=os.environ["POSTGRES_DB"],
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        return True
    except Exception:
        return False


async def check_typesense() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://{TYPESENSE_HOST}:{TYPESENSE_PORT}/health",
                timeout=3.0,
            )
            return resp.status_code == 200
    except Exception:
        return False


async def check_qdrant() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://{QDRANT_HOST}:{QDRANT_PORT}/healthz",
                timeout=3.0,
            )
            return resp.status_code == 200
    except Exception:
        return False

EPS = 1e-9
def categorize(h: float, l: float, v: float) -> str:
    if abs(h - l) < EPS and abs(h - v) < EPS:
        return "tied"
    if h > max(l, v) + EPS:
        return "beat_both"
    if h < min(l, v) - EPS:
        return "lost_both"
    return "between"


@app.get("/health")
async def health() -> dict:
    postgres_ok, typesense_ok, qdrant_ok = await asyncio.gather(
        check_postgres(),
        check_typesense(),
        check_qdrant(),
    )

    backends = {
        "postgres": postgres_ok,
        "typesense": typesense_ok,
        "qdrant": qdrant_ok,
    }
    all_healthy = all(backends.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "backends": backends,
    }


@app.get("/runs")
async def list_runs() -> list[RunSummary]:
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, created_at, backend, dataset, k, embedding_model, "
            " git_sha, concurrency, n_queries, mean_precision, mean_recall, "
            " mean_mrr, mean_ndcg, latency_p50_ms, latency_p95_ms "
            " FROM eval_runs ORDER BY id DESC "
        )
    return [RunSummary(**dict(r)) for r in rows]


@app.get("/runs/{a}/compare/{b}")
async def compare_runs(a: int, b: int) -> list[QueryComparison]:
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT a.query_id, q.text AS query_text, "
            " a.precision_at_k AS a_precision, a.recall_at_k AS a_recall, "
            " a.mrr AS a_mrr, a.ndcg AS a_ndcg, "
            " b.precision_at_k AS b_precision, b.recall_at_k AS b_recall, "
            " b.mrr AS b_mrr, b.ndcg AS b_ndcg "
            " FROM eval_results a "
            " JOIN eval_results b ON a.query_id = b.query_id "
            " JOIN queries q ON q.query_id = a.query_id AND q.split = 'test' "
            " WHERE a.run_id = $1 AND b.run_id = $2",
            a,
            b,
        )
        return [QueryComparison(**dict(r)) for r in rows]

@app.get("/runs/fusion-compare")
async def fusion_compare(hybrid: int, lexical: int, vector: int) -> list[FusionQueryRow]:
    async with app.state.pool.acquire() as conn: 
        rows = await conn.fetch(
            " SELECT q.query_id, q.text AS query_text, "
                " l.ndcg AS lexical_ndcg, v.ndcg AS vector_ndcg, h.ndcg AS hybrid_ndcg "
            " FROM eval_results h"
            " JOIN eval_results l ON l.query_id = h.query_id "
            " JOIN eval_results v ON v.query_id = h.query_id "
            " JOIN queries q ON q.query_id = h.query_id AND q.split = 'test' "
            " WHERE h.run_id = $1 AND l.run_id = $2 AND v.run_id = $3", hybrid, lexical, vector
        )
    return [
        FusionQueryRow(
            query_id=r["query_id"],
            query_text=r["query_text"],
            lexical_ndcg=r["lexical_ndcg"],
            vector_ndcg=r["vector_ndcg"],
            hybrid_ndcg=r["hybrid_ndcg"],
            category=categorize(r["hybrid_ndcg"], r["lexical_ndcg"], r["vector_ndcg"]),
        )
        for r in rows
    ]


@app.get("/runs/{a}/queries/{qid}/compare/{b}")
async def query_drilldown(a: int, qid: str, b: int) -> QueryDrilldown:
    async with app.state.pool.acquire() as conn:
        query_text = await conn.fetchval(
            "SELECT text FROM queries WHERE query_id = $1 AND split = 'test'", qid
        )
        a_rows = await conn.fetch(RANKED_SQL, a, qid)
        b_rows = await conn.fetch(RANKED_SQL, b, qid)
    return QueryDrilldown(
        query_id=qid,
        query_text=query_text,
        a=[RankedDoc(**dict(r)) for r in a_rows],
        b=[RankedDoc(**dict(r)) for r in b_rows],
    )


RANKED_SQL = (
    "SELECT t.rank, t.doc_id, d.title, COALESCE(qr.relevance, 0) AS relevance "
    " FROM eval_results er "
    " CROSS JOIN LATERAL unnest(er.ranked_ids) WITH ORDINALITY AS t(doc_id, rank) "
    " JOIN documents d ON d.doc_id = t.doc_id "
    " LEFT JOIN qrels qr "
    " ON qr.query_id = er.query_id AND qr.doc_id = t.doc_id AND qr.split = 'test' "
    " WHERE er.run_id = $1 AND er.query_id = $2 "
    " ORDER BY t.rank "
)
