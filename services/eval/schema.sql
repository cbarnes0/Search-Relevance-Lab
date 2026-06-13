-- Eval harness persistence. Applied idempotently by the runner on startup
-- (mirrors how services/indexer/ingest.py applies its own schema).
--
-- Two tables:
--   eval_runs    -- one row per run: config, provenance, headline aggregates
--   eval_results -- one row per (run, query): the per-query detail the
--                   drill-down UI reads. Per-query storage is the whole point;
--                   aggregates hide the interesting queries.

CREATE TABLE IF NOT EXISTS eval_runs (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- identity: what experiment this is
    backend         TEXT  NOT NULL,
    dataset         TEXT  NOT NULL,
    k               INT   NOT NULL,
    embedding_model TEXT,            -- NULL for lexical (not applicable)

    -- provenance: how/when it ran
    git_sha         TEXT  NOT NULL,
    concurrency     INT   NOT NULL,

    -- headline aggregates: denormalized from eval_results for a fast
    -- run-list page. Derived (= AVG over the per-query rows), accepted
    -- because eval_results is write-once per run, so they cannot drift.
    n_queries       INT   NOT NULL,
    mean_precision  DOUBLE PRECISION NOT NULL,
    mean_recall     DOUBLE PRECISION NOT NULL,
    mean_mrr        DOUBLE PRECISION NOT NULL,
    mean_ndcg       DOUBLE PRECISION NOT NULL,

    -- latency percentiles (Task 4 populates these; nullable until then)
    latency_p50_ms  DOUBLE PRECISION,
    latency_p95_ms  DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS eval_results (
    run_id          BIGINT NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    query_id        TEXT   NOT NULL,

    precision_at_k  DOUBLE PRECISION NOT NULL,
    recall_at_k     DOUBLE PRECISION NOT NULL,
    mrr             DOUBLE PRECISION NOT NULL,
    ndcg            DOUBLE PRECISION NOT NULL,

    latency_ms      DOUBLE PRECISION NOT NULL,  -- source for the p50/p95 above
    ranked_ids      TEXT[] NOT NULL,            -- ordered; drill-down shows both lists

    PRIMARY KEY (run_id, query_id)
);

-- The drill-down's hot path: "all rows for this run" and joins between two
-- runs on query_id. The composite PK already indexes (run_id, query_id)
-- left-to-right, so run_id lookups are covered.
