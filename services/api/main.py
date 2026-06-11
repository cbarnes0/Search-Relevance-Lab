import asyncio
import os

import asyncpg
import httpx
from fastapi import FastAPI

app = FastAPI(title="Search Relevance Lab API")


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
                f"http://{os.environ['TYPESENSE_HOST']}:{os.environ.get('TYPESENSE_PORT', '8108')}/health",
                timeout=3.0,
            )
            return resp.status_code == 200
    except Exception:
        return False


async def check_qdrant() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://{os.environ['QDRANT_HOST']}:{os.environ.get('QDRANT_PORT', '6333')}/healthz",
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
