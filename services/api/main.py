import asyncio
import os
import time
from contextlib import asynccontextmanager
from typing import Literal

import asyncpg
import httpx
from fastapi import FastAPI, Query
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

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
    yield


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


# --- Backends: identical output shape, different retrieval ------------------
async def run_lexical(client: httpx.AsyncClient, q: str, k: int) -> list[SearchResult]:
    resp = await client.get(
        f"http://{TYPESENSE_HOST}:{TYPESENSE_PORT}/collections/{COLLECTION}/documents/search",
        params={
            "q": q,
            "query_by": "title,text",
            "query_by_weights": "2,1",  # title weighted above text
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


async def run_vector(app: FastAPI, client: httpx.AsyncClient, q: str, k: int) -> list[SearchResult]:
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


@app.get("/search")
async def search(
    q: str,
    backend: Literal["lexical", "vector"] = "lexical",
    k: int = Query(10, ge=1, le=100),
) -> SearchResponse:
    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        if backend == "lexical":
            results = await run_lexical(client, q, k)
        else:
            results = await run_vector(app, client, q, k)
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    return SearchResponse(
        query=q, backend=backend, k=k, latency_ms=latency_ms, results=results
    )


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
