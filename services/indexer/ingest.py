"""Ingest the BEIR/NFCorpus test split into Postgres.

Idempotent: every row is upserted (INSERT ... ON CONFLICT), so re-running never
duplicates. Reads the dataset from the ir_datasets cache mounted at
IR_DATASETS_HOME (populated on the host; see scripts/host_check.py), so no
dataset download happens inside the container.

Run via:  docker compose run --rm indexer python ingest.py
"""

import logging
import os
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import ir_datasets
import psycopg
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# (dataset_id, split) pairs to ingest. The corpus is shared across splits;
# only queries/qrels differ. dev is the held-out tuning set, test the report set.
SPLITS = (
    ("beir/nfcorpus/test", "test"),
    ("beir/nfcorpus/dev", "dev"),
)
BATCH_SIZE = 1000
SCHEMA_FILE = Path(__file__).parent / "schema.sql"


# --- Validation models: every record is checked before it touches the DB ----
class DocumentIn(BaseModel):
    doc_id: str
    title: str = ""
    text: str
    url: str | None = None


class QueryIn(BaseModel):
    query_id: str
    text: str
    url: str | None = None


class QrelIn(BaseModel):
    query_id: str
    doc_id: str
    relevance: int


def connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def apply_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA_FILE.read_text())
    conn.commit()
    log.info("Schema applied")


def _chunked(rows: Sequence[tuple], size: int) -> Iterator[Sequence[tuple]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def upsert(
    conn: psycopg.Connection,
    table: str,
    columns: list[str],
    conflict_cols: list[str],
    rows: Sequence[tuple],
) -> int:
    """Batch-upsert rows. One INSERT carries up to BATCH_SIZE rows — a single
    round-trip per batch instead of one per row."""
    if not rows:
        return 0

    update_cols = [c for c in columns if c not in conflict_cols]
    if update_cols:
        set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        on_conflict = f"DO UPDATE SET {set_clause}"
    else:
        on_conflict = "DO NOTHING"

    row_placeholder = "(" + ", ".join(["%s"] * len(columns)) + ")"
    col_list = ", ".join(columns)
    conflict_list = ", ".join(conflict_cols)

    total = 0
    start = time.perf_counter()
    with conn.cursor() as cur:
        for batch in _chunked(rows, BATCH_SIZE):
            values_sql = ", ".join([row_placeholder] * len(batch))
            params = [value for row in batch for value in row]
            cur.execute(
                f"INSERT INTO {table} ({col_list}) VALUES {values_sql} "
                f"ON CONFLICT ({conflict_list}) {on_conflict}",
                params,
            )
            total += len(batch)
    conn.commit()

    elapsed = time.perf_counter() - start
    rate = total / elapsed if elapsed else 0
    log.info("%s: upserted %d rows in %.2fs (%.0f rows/sec)", table, total, elapsed, rate)
    return total

def main() -> None:
    with connect() as conn:
        apply_schema(conn)

        # The corpus is identical across splits, so load and upsert documents
        # exactly once (from the first split). qrels FK-reference documents,
        # so docs must land before any qrels.
        first_dataset = SPLITS[0][0]
        log.info("Loading documents from %s", first_dataset)
        docs = [
            DocumentIn(doc_id=d.doc_id, title=d.title, text=d.text, url=getattr(d, "url", None))
            for d in ir_datasets.load(first_dataset).docs_iter()
        ]
        log.info("Validated %d docs", len(docs))
        upsert(
            conn, "documents", ["doc_id", "title", "text", "url"], ["doc_id"],
            [(d.doc_id, d.title, d.text, d.url) for d in docs],
        )

        # Queries + qrels are split-specific. Tag each row with its split so
        # dev (tuning) and test (reporting) coexist under the (id, split) PKs.
        for dataset_id, split in SPLITS:
            log.info("Loading %s queries/qrels from %s", split, dataset_id)
            ds = ir_datasets.load(dataset_id)
            queries = [
                QueryIn(query_id=q.query_id, text=q.text, url=getattr(q, "url", None))
                for q in ds.queries_iter()
            ]
            qrels = [
                QrelIn(query_id=r.query_id, doc_id=r.doc_id, relevance=r.relevance)
                for r in ds.qrels_iter()
            ]
            log.info(
                "Validated %d %s queries, %d qrels", len(queries), split, len(qrels)
            )
            upsert(
                conn, "queries", ["query_id", "split", "text", "url"],
                ["query_id", "split"],
                [(q.query_id, split, q.text, q.url) for q in queries],
            )
            upsert(
                conn, "qrels", ["query_id", "doc_id", "split", "relevance"],
                ["query_id", "doc_id", "split"],
                [(r.query_id, r.doc_id, split, r.relevance) for r in qrels],
            )

    log.info("Ingest complete")


if __name__ == "__main__":
    main()
