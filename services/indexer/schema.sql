-- Search Relevance Lab — Phase 2 schema
-- System of record for the corpus, queries, and relevance judgments.
-- Search itself lives in Typesense/Qdrant; Postgres just holds the truth.
--
-- Idempotent: CREATE TABLE IF NOT EXISTS lets the loader (re)apply this safely.

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,            -- natural key from the dataset, e.g. 'MED-10'
    title  TEXT NOT NULL DEFAULT '',
    text   TEXT NOT NULL,
    url    TEXT                         -- provenance (PubMed), nullable
);

CREATE TABLE IF NOT EXISTS queries (
    query_id TEXT NOT NULL,             -- e.g. 'PLAIN-2'
    split    TEXT NOT NULL,             -- 'test' | 'train' | 'dev'
    text     TEXT NOT NULL,
    url      TEXT,
    PRIMARY KEY (query_id, split)       -- same query_id can recur across splits
);

CREATE TABLE IF NOT EXISTS qrels (
    query_id  TEXT NOT NULL,
    doc_id    TEXT NOT NULL,
    split     TEXT NOT NULL,
    relevance SMALLINT NOT NULL,        -- graded: 0 / 1 / 2 (NFCorpus)
    PRIMARY KEY (query_id, doc_id, split),
    -- Enforce that a judgment can't point at a phantom document. We deliberately
    -- do NOT FK query_id -> queries, so qrels for an unloaded split won't fail.
    FOREIGN KEY (doc_id) REFERENCES documents (doc_id)
);

-- Reverse lookup: "which queries judge this document?" (Phase 3).
CREATE INDEX IF NOT EXISTS idx_qrels_doc_id ON qrels (doc_id);
