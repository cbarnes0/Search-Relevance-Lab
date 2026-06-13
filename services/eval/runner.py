import asyncio
import os
import subprocess
from pathlib import Path
from statistics import mean

import httpx
import psycopg

from metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank

SCHEMA_FILE = Path(__file__).parent / "schema.sql"
DATASET = "beir/nfcorpus/test"


def apply_schema(conn: psycopg.Connection) -> None:
    """Create the eval tables if they don't exist (idempotent).

    Mirrors services/indexer/ingest.py: the DDL uses CREATE TABLE IF NOT
    EXISTS, so running this on every startup is safe and cheap.
    """
    conn.execute(SCHEMA_FILE.read_text())
    conn.commit()


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def load_queries() -> dict[str, str]:

    with connect() as conn:
        rows = conn.execute(
            "SELECT query_id, text FROM queries WHERE split = %s", ("test",)
        ).fetchall()
    return {query_id: text for query_id, text in rows}


def load_qrels() -> dict[str, dict[str, int]]:

    with connect() as conn:
        rows = conn.execute(
            "SELECT query_id, doc_id, relevance FROM qrels WHERE split = %s", ("test",)
        ).fetchall()
        qrels = {}
        for query_id, doc_id, relevance in rows:
            inner = qrels.setdefault(query_id, {})
            inner[doc_id] = relevance

        return qrels


async def run_query(client, sem, query_id, text, backend, k, qrels):
    async with sem:
        resp = await client.get(
            "/search", params={"q": text, "backend": backend, "k": k}
        )

        resp.raise_for_status()
        body = resp.json()

        ranked_ids = [entry["doc_id"] for entry in body["results"]]
        latency = body["latency_ms"]

        ndcg = ndcg_at_k(ranked_ids, qrels, k)
        mrr = reciprocal_rank(ranked_ids, qrels, k)
        p_at_k = precision_at_k(ranked_ids, qrels, k)
        r_at_k = recall_at_k(ranked_ids, qrels, k)

        return {
            "query_id": query_id,
            "ndcg": ndcg,
            "mrr": mrr,
            "precision_at_k": p_at_k,
            "recall_at_k": r_at_k,
            "latency_ms": latency,
            "ranked_ids": ranked_ids,
        }


async def run_eval(backend, k, concurrency):

    queries = load_queries()
    qrels = load_qrels()

    git_sha = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout
    ).strip()

    async with httpx.AsyncClient(
        base_url=os.getenv("API_URL", "http://localhost:8000")
    ) as client:
        config = (await client.get("/config")).raise_for_status().json()
        meta = {
            "git_sha": git_sha,
            "embedding_model": config["embedding_model"]
            if backend == "vector"
            else None,
            "backend": backend,
            "k": k,
            "concurrency": concurrency,
            "dataset": DATASET,
        }
        sem = asyncio.Semaphore(concurrency)

        coros = [
            run_query(client, sem, qid, text, backend, k, qrels[qid])
            for (qid, text) in queries.items()
        ]

        records = await asyncio.gather(*coros)

    mean_ndcg = mean(r["ndcg"] for r in records)
    mean_mrr = mean(r["mrr"] for r in records)
    mean_p = mean(r["precision_at_k"] for r in records)
    mean_r = mean(r["recall_at_k"] for r in records)
    mean_lat = mean(r["latency_ms"] for r in records)

    print(
        f"{backend} k={k}: P@{k}={mean_p:.4f} R@{k}={mean_r:.4f} "
        f"MRR={mean_mrr:.4f} nDCG@{k}={mean_ndcg:.4f} "
        f"mean_latency={mean_lat:.4f}ms n={len(records)}"
    )

    return records, meta


def save_run(conn: psycopg.Connection, meta: dict, records: list[dict]) -> int:

    if not records:
        return 0

    mean_ndcg = mean(r["ndcg"] for r in records)
    mean_precision = mean(r["precision_at_k"] for r in records)
    mean_recall = mean(r["recall_at_k"] for r in records)
    mean_mrr = mean(r["mrr"] for r in records)
    n_queries = len(records)

    with conn.transaction():
        run_id = conn.execute(
            "INSERT INTO eval_runs (backend, dataset, k, embedding_model, "
            "git_sha, concurrency, n_queries, mean_precision, mean_recall, "
            "mean_mrr, mean_ndcg) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                meta["backend"],
                meta["dataset"],
                meta["k"],
                meta["embedding_model"],
                meta["git_sha"],
                meta["concurrency"],
                n_queries,
                mean_precision,
                mean_recall,
                mean_mrr,
                mean_ndcg,
            ),
        ).fetchone()[0]

        for r in records:
            conn.execute(
                "INSERT INTO eval_results (run_id, query_id, precision_at_k, "
                "recall_at_k, mrr, ndcg, latency_ms, ranked_ids) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    run_id,
                    r["query_id"],
                    r["precision_at_k"],
                    r["recall_at_k"],
                    r["mrr"],
                    r["ndcg"],
                    r["latency_ms"],
                    r["ranked_ids"],
                ),
            )

    return run_id


if __name__ == "__main__":
    with connect() as conn:
        apply_schema(conn)
        for backend in ("lexical", "vector"):
            records, meta = asyncio.run(run_eval(backend, k=10, concurrency=8))
            run_id = save_run(conn, meta, records)
            print(f"saved run {run_id}: {backend}")
