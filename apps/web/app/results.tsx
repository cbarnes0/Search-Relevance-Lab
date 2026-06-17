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
    <span className="muted" style={{ fontSize: "0.85rem" }}>
      {backend} · {latencyMs.toFixed(1)} ms
    </span>
  );
}

function ResultCard({ result }: { result: SearchResult }) {
  return (
    <li className="result-item">
      <div className="result-item__meta">
        #{result.rank} · {result.doc_id} · score {formatScore(result.score)}
      </div>
      <div className="result-item__title">{result.title}</div>
      <div className="result-item__snippet">{result.snippet}…</div>
    </li>
  );
}

function ResultColumn({ heading, data }: { heading: string; data: SearchResponse | null }) {
  return (
    <section className="column">
      <header className="column__header">
        <h2>{heading}</h2>
        {data && <LatencyBadge backend={data.backend} latencyMs={data.latency_ms} />}
      </header>
      {data === null ? (
        <p className="error">Backend unreachable</p>
      ) : data.results.length === 0 ? (
        <p className="muted">No results</p>
      ) : (
        <ol className="result-list">
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
    <div className="columns">
      <ResultColumn heading="Lexical (Typesense)" data={lexical} />
      <ResultColumn heading="Vector (Qdrant)" data={vector} />
    </div>
  );
}
