"""Host-side acquisition check for NFCorpus.

Downloads the BEIR/NFCorpus test split via ir_datasets into ./data/ir_datasets
(a host directory we will bind-mount into the indexer container) and prints the
exact record field names so we can lock the Postgres schema against reality.

Run from the repo root:  python scripts/host_check.py
"""

import os

# Cache into a repo-local, host-visible dir (will be the bind-mount target).
os.environ["IR_DATASETS_HOME"] = os.path.abspath("./data/ir_datasets")

import ir_datasets  # noqa: E402  (import after env var is set)

ds = ir_datasets.load("beir/nfcorpus/test")

doc = next(ds.docs_iter())
print("DOC FIELDS  :", doc._fields)
print("DOC SAMPLE  :", doc)

q = next(ds.queries_iter())
print("QUERY FIELDS:", q._fields)
print("QUERY SAMPLE:", q)

qr = next(ds.qrels_iter())
print("QREL FIELDS :", qr._fields)
print("QREL SAMPLE :", qr)

print("COUNTS      : docs=%d queries=%d qrels=%d" % (
    ds.docs_count(), ds.queries_count(), ds.qrels_count()
))
