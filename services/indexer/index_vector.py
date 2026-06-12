"""Embed the corpus and index it into Qdrant for vector (semantic) search.

Idempotent: the Qdrant collection is recreated each run, and each point's ID is a
deterministic UUID derived from doc_id, so re-running upserts in place rather than
duplicating.

Documents are encoded WITHOUT an instruction prefix (bge convention). Queries get
a retrieval prefix at search time — see query_vector.py.

Run via:  docker compose run --rm indexer python index_vector.py
"""

import logging
import os
import time
import uuid
from collections.abc import Iterator, Sequence

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

COLLECTION = "documents"
MODEL_NAME = os.environ["EMBEDDING_MODEL"]
EMBEDDING_DIM = int(os.environ["EMBEDDING_DIM"])
ENCODE_BATCH = 64   # texts per forward pass (throughput vs. memory)
CHUNK = 512         # docs encoded+upserted per loop (progress granularity)


def pg_connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )


def qdrant() -> QdrantClient:
    return QdrantClient(
        host=os.environ["QDRANT_HOST"],
        port=int(os.environ.get("QDRANT_PORT", "6333")),
    )


def recreate_collection(client: QdrantClient) -> None:
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
        log.info("Dropped existing '%s' collection", COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    log.info("Created '%s' collection (dim=%d, cosine)", COLLECTION, EMBEDDING_DIM)


def fetch_documents(conn: psycopg.Connection) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute("SELECT doc_id, title, text, url FROM documents")
        return cur.fetchall()


def _chunked(rows: Sequence[tuple], size: int) -> Iterator[Sequence[tuple]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def main() -> None:
    log.info("Loading model %s", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)
    dim = model.get_sentence_embedding_dimension()
    if dim != EMBEDDING_DIM:
        raise RuntimeError(f"EMBEDDING_DIM={EMBEDDING_DIM} but model emits dim={dim}")

    client = qdrant()
    recreate_collection(client)

    with pg_connect() as conn:
        rows = fetch_documents(conn)
    total = len(rows)
    log.info("Encoding %d documents", total)

    done = 0
    start = time.perf_counter()
    for chunk in _chunked(rows, CHUNK):
        # Embed title + abstract together; normalize for cosine.
        texts = [f"{title}. {text}".strip() for _, title, text, _ in chunk]
        vectors = model.encode(
            texts,
            batch_size=ENCODE_BATCH,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        points = [
            PointStruct(
                # Qdrant IDs must be int/UUID — derive a stable UUID from doc_id.
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, doc_id)),
                vector=vector.tolist(),
                payload={"doc_id": doc_id, "title": title, "url": url or "", "text": text},
            )
            for (doc_id, title, text, url), vector in zip(chunk, vectors)
        ]
        client.upsert(collection_name=COLLECTION, points=points)
        done += len(chunk)
        elapsed = time.perf_counter() - start
        rate = done / elapsed if elapsed else 0
        log.info("Embedded+upserted %d/%d (%.0f docs/sec)", done, total, rate)

    count = client.count(COLLECTION).count
    log.info("Qdrant reports %d points in '%s'", count, COLLECTION)
    log.info("Vector indexing complete")


if __name__ == "__main__":
    main()
