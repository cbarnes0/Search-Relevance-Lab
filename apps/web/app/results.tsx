// All server components: they take props and render markup, nothing more. No
// "use client" — none of them need to do anything after the HTML reaches the
// browser. Rendered on the server, shipped as plain HTML.

import type { SearchResponse, SearchResult } from "./types";

// Lexical scores are huge integers (Typesense text_match); vector scores are
// cosine in 0..1. Format each on its own scale — they are NOT comparable.
function formatScore(score: number): string {
  return score >= 1000 ? score.toExponential(2) : score.toFixed(4);
}

function LatencyBadge({ backend, latencyMs }: { backend: string; latencyMs: number }) {
  return (
    <span style={{ fontSize: "0.85rem", color: "#888" }}>
      {backend} · {latencyMs.toFixed(1)} ms
    </span>
  );
}

function ResultCard({ result }: { result: SearchResult }) {
  return (
    <li
      style={{
        listStyle: "none",
        padding: "0.75rem 0",
        borderBottom: "1px solid #222",
      }}
    >
      <div style={{ fontSize: "0.8rem", color: "#666", marginBottom: "0.25rem" }}>
        #{result.rank} · {result.doc_id} · score {formatScore(result.score)}
      </div>
      <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{result.title}</div>
      <div style={{ fontSize: "0.9rem", color: "#aaa" }}>{result.snippet}…</div>
    </li>
  );
}

function ResultColumn({ heading, data }: { heading: string; data: SearchResponse | null }) {
  return (
    <section style={{ flex: 1, minWidth: 0 }}>
      <header
        style={{
          display: "flex",
          alignItems: "baseline",
          justifyContent: "space-between",
          marginBottom: "0.5rem",
        }}
      >
        <h2 style={{ fontSize: "1.1rem", margin: 0 }}>{heading}</h2>
        {data && <LatencyBadge backend={data.backend} latencyMs={data.latency_ms} />}
      </header>
      {data === null ? (
        <p style={{ color: "#f87171" }}>Backend unreachable</p>
      ) : data.results.length === 0 ? (
        <p style={{ color: "#888" }}>No results</p>
      ) : (
        <ol style={{ margin: 0, padding: 0 }}>
          {data.results.map((r) => (
            <ResultCard key={`${r.doc_id}-${r.rank}`} result={r} />
          ))}
        </ol>
      )}
    </section>
  );
}

export function ResultsComparison({
  lexical,
  vector,
}: {
  lexical: SearchResponse | null;
  vector: SearchResponse | null;
}) {
  return (
    <div style={{ display: "flex", gap: "2.5rem", alignItems: "flex-start" }}>
      <ResultColumn heading="Lexical (Typesense)" data={lexical} />
      <ResultColumn heading="Vector (Qdrant)" data={vector} />
    </div>
  );
}
