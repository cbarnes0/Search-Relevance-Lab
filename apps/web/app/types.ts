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
