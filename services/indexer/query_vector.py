"""Quick semantic-search check against Qdrant.

Embeds a query and prints the top-k nearest documents. Use it to see the lexical
gap close: 'heart attack' should surface 'myocardial infarction' passages that
share none of the query's tokens.

Run via:  docker compose run --rm indexer python query_vector.py "heart attack"
"""

import os
import sys

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

COLLECTION = "documents"
# bge-*-en-v1.5 recommends prefixing QUERIES (not documents) for retrieval.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def main() -> None:
    query = " ".join(sys.argv[1:]) or "heart attack"

    model = SentenceTransformer(os.environ["EMBEDDING_MODEL"])
    vector = model.encode(QUERY_PREFIX + query, normalize_embeddings=True).tolist()

    client = QdrantClient(
        host=os.environ["QDRANT_HOST"],
        port=int(os.environ.get("QDRANT_PORT", "6333")),
    )
    hits = client.search(
        collection_name=COLLECTION,
        query_vector=vector,
        limit=5,
        with_payload=True,
    )

    print(f"\nQuery: {query!r}\n")
    for rank, hit in enumerate(hits, 1):
        title = hit.payload["title"][:80]
        print(f"{rank}. score={hit.score:.4f}  {hit.payload['doc_id']}  {title}")


if __name__ == "__main__":
    main()
