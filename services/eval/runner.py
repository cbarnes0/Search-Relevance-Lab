import asyncio
import os
import subprocess
from pathlib import Path
from statistics import mean, median, quantiles

import httpx
import psycopg

from metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank

SCHEMA_FILE = Path(__file__).parent / "schema.sql"

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


def load_queries(split: str) -> dict[str, str]:

    with connect() as conn:
        rows = conn.execute(
            "SELECT query_id, text FROM queries WHERE split = %s", (split,)
        ).fetchall()
    return {query_id: text for query_id, text in rows}


def load_qrels(split: str) -> dict[str, dict[str, int]]:

    with connect() as conn:
        rows = conn.execute(
            "SELECT query_id, doc_id, relevance FROM qrels WHERE split = %s", (split,)
        ).fetchall()
        qrels = {}
        for query_id, doc_id, relevance in rows:
            inner = qrels.setdefault(query_id, {})
            inner[doc_id] = relevance

        return qrels


async def run_query(client, sem, query_id, text, backend, k, qrels, fusion_method=None, rrf_k=None, alpha=None, max_retries=3):
    async with sem:
        params = {"q": text, "backend": backend, "k": k}
        if backend == "hybrid":
            params["fusion_method"] = fusion_method
            if rrf_k is not None:
                params["rrf_k"] = rrf_k
            if alpha is not None:
                params["alpha"] = alpha

        # Retry transient backend failures (Typesense 408 under sweep load,
        # 5xx, timeouts) so one flaky query doesn't abort a long batch run.
        # Persistent failures still raise -- never silently drop a query, which
        # would change n and bias the mean metrics.
        for attempt in range(max_retries):
            try:
                resp = await client.get("/search", params=params)
                resp.raise_for_status()
                break
            except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
                transient = isinstance(exc, httpx.TimeoutException) or (
                    exc.response.status_code in (408, 429, 500, 502, 503, 504)
                )
                if not transient or attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.5 * (attempt + 1))

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


async def run_eval(backend, k, concurrency, split="test", fusion_method=None, rrf_k=None, alpha=None):

    queries = load_queries(split)
    qrels = load_qrels(split)

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
            if backend in ("vector", "hybrid")
            else None,
            "backend": backend,
            "k": k,
            "concurrency": concurrency,
            "dataset": f"beir/nfcorpus/{split}",
            "fusion_method": fusion_method,
            "rrf_k": rrf_k,
            "alpha": alpha
        }
        sem = asyncio.Semaphore(concurrency)

        coros = [
            run_query(client, sem, qid, text, backend, k, qrels[qid], fusion_method=fusion_method, rrf_k=rrf_k, alpha=alpha)
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
    p50 = median(r["latency_ms"] for r in records)
    p95 = quantiles((r["latency_ms"] for r in records), n=100)[94]

    with conn.transaction():
        run_id = conn.execute(
            "INSERT INTO eval_runs (backend, dataset, k, embedding_model, "
            "git_sha, concurrency, n_queries, mean_precision, mean_recall, "
            "mean_mrr, mean_ndcg, latency_p50_ms, latency_p95_ms, fusion_method, rrf_k, alpha) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
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
                p50,
                p95,
                meta["fusion_method"],
                meta["rrf_k"],
                meta["alpha"]
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
        for method, rrf_k, alpha in (("rrf", 60, None), ("weighted", None, 0.5)):
            records, meta = asyncio.run(
                run_eval("hybrid", k=10, concurrency=8,
                         fusion_method=method, rrf_k=rrf_k, alpha=alpha)
            )
            run_id = save_run(conn, meta, records)
            print(f"saved run {run_id}: {method}")
        # 1. alpha sweep on DEV (weighted)
        alpha_results = []
        for alpha in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            records, _ = asyncio.run(run_eval("hybrid", k=10, concurrency=4, split="dev",
                                              fusion_method="weighted", alpha=alpha))
            ndcg = mean(r["ndcg"] for r in records)
            alpha_results.append((alpha, ndcg))

        best_alpha, best_alpha_ndcg = max(alpha_results, key=lambda pair: pair[1])
        print("alpha sweep (dev):", alpha_results)
        print(f"best alpha={best_alpha} dev nDCG={best_alpha_ndcg:.4f}")

        # 2. rrf k sweep on DEV
        rrf_k_results = []
        for rrf_k in [1, 10, 30, 60, 100, 200]:
            records, _ = asyncio.run(run_eval("hybrid", k=10, concurrency=4, split="dev",
                                              fusion_method="rrf", rrf_k=rrf_k))
            ndcg = mean(r["ndcg"] for r in records)
            rrf_k_results.append((rrf_k, ndcg))

        best_k, best_k_ndcg = max(rrf_k_results, key=lambda pair: pair[1])
        print("rrf k sweep (dev):", rrf_k_results)
        print(f"best k={best_k} dev nDCG={best_k_ndcg:.4f}")

        # 3. report tuned params on TEST (the honest headline numbers) and save
        records, meta = asyncio.run(run_eval("hybrid", k=10, concurrency=8, split="test",
                                             fusion_method="weighted", alpha=best_alpha))
        run_id = save_run(conn, meta, records)
        print(f"saved tuned weighted run {run_id}: alpha={best_alpha}")

        records, meta = asyncio.run(run_eval("hybrid", k=10, concurrency=8, split="test",
                                             fusion_method="rrf", rrf_k=best_k))
        run_id = save_run(conn, meta, records)
        print(f"saved tuned rrf run {run_id}: k={best_k}")
