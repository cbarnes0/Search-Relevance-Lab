"""Index the corpus into Typesense for lexical (keyword) search.

Reads documents from Postgres and (re)builds the Typesense collection. Idempotent:
the collection is recreated from a clean schema each run, and documents are
imported with action='upsert' keyed on `id` (the dataset doc_id), so re-running
never duplicates.

Note: field *weighting* (title above text) is NOT set here — it's a search-time
parameter (query_by_weights) applied in the search endpoint. This schema only
declares which fields are searchable.

Run via:  docker compose run --rm indexer python index_lexical.py
"""

import logging
import os
import time

import psycopg
import typesense

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

COLLECTION = "documents"
BATCH_SIZE = 1000

SCHEMA = {
    "name": COLLECTION,
    "fields": [
        # stem=True applies Snowball stemming at index + query time, so
        # morphological variants (obese/obesity) fold to one root — closing
        # part of the gap to Anserini's BM25, which stems by default.
        {"name": "title", "type": "string", "stem": True},
        {"name": "text", "type": "string", "stem": True},
        # Returnable in results but not searchable — no value matching query text
        # against a URL. No default_sorting_field: rank by text match score.
        {"name": "url", "type": "string", "index": False, "optional": True},
    ],
}


def pg_connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def ts_client() -> typesense.Client:
    return typesense.Client(
        {
            "nodes": [
                {
                    "host": os.environ["TYPESENSE_HOST"],
                    "port": os.environ.get("TYPESENSE_PORT", "8108"),
                    "protocol": "http",
                }
            ],
            "api_key": os.environ["TYPESENSE_API_KEY"],
            "connection_timeout_seconds": 10,
        }
    )


def recreate_collection(client: typesense.Client) -> None:
    try:
        client.collections[COLLECTION].delete()
        log.info("Dropped existing '%s' collection", COLLECTION)
    except typesense.exceptions.ObjectNotFound:
        pass
    client.collections.create(SCHEMA)
    log.info("Created '%s' collection", COLLECTION)


def fetch_documents(conn: psycopg.Connection) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT doc_id, title, text, url FROM documents")
        rows = cur.fetchall()
    # Typesense's special `id` field = dataset doc_id → upserts are idempotent.
    return [
        {"id": doc_id, "title": title, "text": text, "url": url or ""}
        for doc_id, title, text, url in rows
    ]


def _chunked(items: list[dict], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def index(client: typesense.Client, docs: list[dict]) -> None:
    total = len(docs)
    done = 0
    start = time.perf_counter()
    for batch in _chunked(docs, BATCH_SIZE):
        results = client.collections[COLLECTION].documents.import_(
            batch, {"action": "upsert"}
        )
        failures = [r for r in results if not r.get("success")]
        if failures:
            raise RuntimeError(f"Typesense import failed for {len(failures)} docs: {failures[:3]}")
        done += len(batch)
        log.info("Indexed %d/%d", done, total)

    elapsed = time.perf_counter() - start
    rate = total / elapsed if elapsed else 0
    log.info("Indexed %d documents in %.2fs (%.0f docs/sec)", total, elapsed, rate)


def main() -> None:
    client = ts_client()
    recreate_collection(client)

    with pg_connect() as conn:
        docs = fetch_documents(conn)
    log.info("Fetched %d documents from Postgres", len(docs))

    index(client, docs)

    count = client.collections[COLLECTION].retrieve()["num_documents"]
    log.info("Typesense reports %d documents in '%s'", count, COLLECTION)
    log.info("Lexical indexing complete")


if __name__ == "__main__":
    main()
