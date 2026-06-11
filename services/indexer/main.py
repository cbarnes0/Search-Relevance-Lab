import logging
import os
import sys

import typesense
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

TYPESENSE_COLLECTION = "indexer_smoke_test"
QDRANT_COLLECTION = "indexer_smoke_test"


def run_typesense() -> None:
    client = typesense.Client(
        {
            "nodes": [
                {
                    "host": os.environ["TYPESENSE_HOST"],
                    "port": os.environ.get("TYPESENSE_PORT", "8108"),
                    "protocol": "http",
                }
            ],
            "api_key": os.environ["TYPESENSE_API_KEY"],
            "connection_timeout_seconds": 5,
        }
    )

    # Clean up from any previous run
    try:
        client.collections[TYPESENSE_COLLECTION].delete()
        log.info("Typesense: deleted existing collection")
    except Exception:
        pass

    client.collections.create(
        {
            "name": TYPESENSE_COLLECTION,
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "title", "type": "string"},
            ],
        }
    )
    log.info("Typesense: created collection '%s'", TYPESENSE_COLLECTION)

    client.collections[TYPESENSE_COLLECTION].documents.create(
        {"id": "1", "title": "Hello from the indexer"}
    )
    log.info("Typesense: wrote document")

    doc = client.collections[TYPESENSE_COLLECTION].documents["1"].retrieve()
    assert doc["title"] == "Hello from the indexer", f"unexpected doc: {doc}"
    log.info("Typesense: read back document — title=%r", doc["title"])

    client.collections[TYPESENSE_COLLECTION].delete()
    log.info("Typesense: cleaned up collection")


def run_qdrant() -> None:
    client = QdrantClient(
        host=os.environ["QDRANT_HOST"],
        port=int(os.environ.get("QDRANT_PORT", "6333")),
    )

    # Clean up from any previous run
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        client.delete_collection(QDRANT_COLLECTION)
        log.info("Qdrant: deleted existing collection")

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=3, distance=Distance.COSINE),
    )
    log.info("Qdrant: created collection '%s'", QDRANT_COLLECTION)

    client.upsert(
        collection_name=QDRANT_COLLECTION,
        points=[
            PointStruct(
                id=1,
                vector=[0.1, 0.2, 0.3],
                payload={"title": "Hello from the indexer"},
            )
        ],
    )
    log.info("Qdrant: wrote point")

    results = client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=[1],
        with_payload=True,
    )
    assert results[0].payload["title"] == "Hello from the indexer"
    log.info("Qdrant: read back point — payload=%r", results[0].payload)

    client.delete_collection(QDRANT_COLLECTION)
    log.info("Qdrant: cleaned up collection")


def main() -> None:
    log.info("Indexer starting")

    errors: list[str] = []

    try:
        run_typesense()
        log.info("Typesense: OK")
    except Exception as e:
        log.error("Typesense: FAILED — %s", e)
        errors.append("typesense")

    try:
        run_qdrant()
        log.info("Qdrant: OK")
    except Exception as e:
        log.error("Qdrant: FAILED — %s", e)
        errors.append("qdrant")

    if errors:
        log.error("Indexer finished with errors: %s", errors)
        sys.exit(1)

    log.info("Indexer finished successfully")


if __name__ == "__main__":
    main()
