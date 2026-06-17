// Mirrors the API's normalized search contract (services/api/main.py).
export type SearchResult = {
  doc_id: string;
  title: string;
  snippet: string;
  score: number;
  rank: number;
};

export type SearchResponse = {
  query: string;
  backend: string;
  k: number;
  latency_ms: number;
  results: SearchResult[];
};

// Mirrors the API's RunSummary model (services/api/main.py, GET /runs).
export type RunSummary = {
  id: number;
  created_at: string; // ISO timestamp
  backend: string;
  dataset: string;
  k: number;
  embedding_model: string | null; // null for lexical
  fusion_method: string | null; // null for single-backend runs
  rrf_k: number | null; // set only for fusion_method='rrf'
  alpha: number | null; // set only for fusion_method='weighted'
  git_sha: string;
  concurrency: number;
  n_queries: number;
  mean_precision: number;
  mean_recall: number;
  mean_mrr: number;
  mean_ndcg: number;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
};

// Mirrors the API's QueryComparison model (GET /runs/{a}/compare/{b}).
// One row per query present in both runs; a_* = run A, b_* = run B.
export type QueryComparison = {
  query_id: string;
  query_text: string;
  a_precision: number;
  a_recall: number;
  a_mrr: number;
  a_ndcg: number;
  b_precision: number;
  b_recall: number;
  b_mrr: number;
  b_ndcg: number;
};

// Mirrors the API's FusionQueryRow model (GET /runs/fusion-compare).
export type FusionCategory = "beat_both" | "lost_both" | "between" | "tied";
export type FusionQueryRow = {
  query_id: string;
  query_text: string;
  lexical_ndcg: number;
  vector_ndcg: number;
  hybrid_ndcg: number;
  category: FusionCategory;
};

// Mirrors the API's drill-down models (GET /runs/{a}/queries/{qid}/compare/{b}).
export type RankedDoc = {
  rank: number;
  doc_id: string;
  title: string;
  relevance: number; // 0 = not relevant, >0 = relevant grade
};

export type QueryDrilldown = {
  query_id: string;
  query_text: string;
  a: RankedDoc[];
  b: RankedDoc[];
};
