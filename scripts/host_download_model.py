"""Host-side download of the embedding model into ./data/hf_cache.

The container's network is locked down, so we fetch the model weights on the host
and bind-mount the cache into the indexer (HF_HOME=/data/hf_cache). Run from the
repo root:  python scripts/host_download_model.py
"""

import os

os.environ["HF_HOME"] = os.path.abspath("./data/hf_cache")

from sentence_transformers import SentenceTransformer  # noqa: E402

MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

model = SentenceTransformer(MODEL)
print(f"Downloaded {MODEL} -> ./data/hf_cache")
print("Embedding dimension:", model.get_sentence_embedding_dimension())
