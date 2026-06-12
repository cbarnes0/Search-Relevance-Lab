// Server component (Pattern A). Reads the query from the URL, fetches BOTH
// backends server-side in parallel, and renders results as HTML. The fetch runs
// inside the web container, so it uses the internal Docker hostname (API_URL =
// http://api:8000) at runtime — the browser never calls the API directly.

import SearchBox from "./SearchBox";
import { ResultsComparison } from "./results";
import type { SearchResponse } from "./types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function search(
  q: string,
  backend: "lexical" | "vector",
): Promise<SearchResponse | null> {
  try {
    const res = await fetch(
      `${API_URL}/search?q=${encodeURIComponent(q)}&backend=${backend}&k=10`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q } = await searchParams; // Next 16: searchParams is async
  const query = q?.trim() ?? "";

  let lexical: SearchResponse | null = null;
  let vector: SearchResponse | null = null;
  if (query) {
    [lexical, vector] = await Promise.all([
      search(query, "lexical"),
      search(query, "vector"),
    ]);
  }

  return (
    <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
      <h1 style={{ marginBottom: "0.25rem" }}>Search Relevance Lab</h1>
      <p style={{ color: "#888", marginBottom: "2rem" }}>
        Lexical vs. vector retrieval — NFCorpus
      </p>

      <SearchBox initialQuery={query} />

      {query ? (
        <ResultsComparison lexical={lexical} vector={vector} />
      ) : (
        <p style={{ color: "#888" }}>Enter a query to compare backends.</p>
      )}
    </main>
  );
}
