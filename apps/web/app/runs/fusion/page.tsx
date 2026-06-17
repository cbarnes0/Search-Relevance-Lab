import Link from "next/link";

import type { FusionCategory, FusionQueryRow, RunSummary } from "../../types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

// The filter buttons. "all" is the no-filter default; the rest match the
// API's category union.
const FILTERS = ["all", "beat_both", "lost_both", "between", "tied"] as const;
type Filter = (typeof FILTERS)[number];

async function getRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_URL}/runs`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

async function getFusion(
  hybrid: number,
  lexical: number,
  vector: number,
): Promise<FusionQueryRow[]> {
  const res = await fetch(
    `${API_URL}/runs/fusion-compare?hybrid=${hybrid}&lexical=${lexical}&vector=${vector}`,
    { cache: "no-store" },
  );
  if (!res.ok) return [];
  return res.json();
}

const cell: React.CSSProperties = {
  padding: "0.4rem 0.75rem",
  borderBottom: "1px solid #222",
  textAlign: "right",
  whiteSpace: "nowrap",
};
const leftCell: React.CSSProperties = { ...cell, textAlign: "left" };

// Category -> colour, for the category cell.
const categoryColor: Record<FusionCategory, string> = {
  beat_both: "#4ade80", // green
  lost_both: "#f87171", // red
  between: "#aaa",
  tied: "#666",
};

export default async function FusionPage({
  searchParams,
}: {
  searchParams: Promise<{
    hybrid?: string;
    lexical?: string;
    vector?: string;
    filter?: string;
  }>;
}) {
  const params = await searchParams;
  const hybrid = Number(params.hybrid);
  const lexical = Number(params.lexical);
  const vector = Number(params.vector);
  // Validate filter against the allowed set; fall back to "all".
  const filter: Filter = FILTERS.includes(params.filter as Filter)
    ? (params.filter as Filter)
    : "all";

  if (!hybrid || !lexical || !vector) {
    return (
      <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
        <p style={{ color: "#f87171" }}>
          Need hybrid, lexical, and vector run ids, e.g.{" "}
          <code>?hybrid=19&lexical=15&vector=16</code>.{" "}
          <Link href="/runs">← all runs</Link>
        </p>
      </main>
    );
  }

  const [runs, rows] = await Promise.all([
    getRuns(),
    getFusion(hybrid, lexical, vector),
  ]);

  // Look up the three run summaries for the header (labels + fusion params).
  const hybridRun = runs.find((r) => r.id === hybrid) ?? null;
  const lexicalRun = runs.find((r) => r.id === lexical) ?? null;
  const vectorRun = runs.find((r) => r.id === vector) ?? null;

  // order by hybrid's advantage over the better single, descending:
  //   hybrid_ndcg - max(lexical_ndcg, vector_ndcg)
  // so beat_both floats to the top and lost_both sinks.
  const sorted = [...rows].sort((a, b) => {
    const advantageA = a.hybrid_ndcg - Math.max(a.lexical_ndcg, a.vector_ndcg);
    const advantageB = b.hybrid_ndcg - Math.max(b.lexical_ndcg, b.vector_ndcg);
    return advantageB - advantageA; // Descending order
  });

  // `category` matches. Server-side: just .filter() over `sorted`.
  const visible = filter === "all" 
    ? sorted 
    : sorted.filter((row) => row.category === filter);

  return (
    <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>Fusion comparison</h1>
      <p style={{ color: "#888", marginBottom: "1.5rem" }}>
        hybrid {hybrid} vs vector {vector} vs lexical {lexical}.{" "}
        <Link href="/runs">← all runs</Link>
      </p>

      <section style={{ display: "flex", gap: "1.5rem", marginBottom: "2rem" }}>
        <div style={{ flex: 1, padding: "1rem", border: "1px solid #333", borderRadius: "6px" }}>
          <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1rem", color: "#888" }}>Lexical</h3>
          {lexicalRun ? (
            <div>
              <div style={{ fontSize: "1.25rem", fontWeight: "bold" }}>{lexicalRun.mean_ndcg.toFixed(4)}</div>
              <div style={{ fontSize: "0.85rem", color: "#aaa", marginTop: "0.25rem" }}>Backend: {lexicalRun.backend}</div>
            </div>
          ) : (
            <p style={{ color: "#f87171", margin: 0 }}>Run {lexical} not found</p>
          )}
        </div>

        <div style={{ flex: 1, padding: "1rem", border: "1px solid #333", borderRadius: "6px" }}>
          <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1rem", color: "#888" }}>Vector</h3>
          {vectorRun ? (
            <div>
              <div style={{ fontSize: "1.25rem", fontWeight: "bold" }}>{vectorRun.mean_ndcg.toFixed(4)}</div>
              <div style={{ fontSize: "0.85rem", color: "#aaa", marginTop: "0.25rem" }}>Backend: {vectorRun.backend}</div>
            </div>
          ) : (
            <p style={{ color: "#f87171", margin: 0 }}>Run {vector} not found</p>
          )}
        </div>

        <div style={{ flex: 1, padding: "1rem", border: "1px solid #333", borderRadius: "6px" }}>
          <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1rem", color: "#888" }}>Hybrid</h3>
          {hybridRun ? (
            <div>
              <div style={{ fontSize: "1.25rem", fontWeight: "bold" }}>{hybridRun.mean_ndcg.toFixed(4)}</div>
              <div style={{ fontSize: "0.85rem", color: "#aaa", marginTop: "0.25rem" }}>Backend: {hybridRun.backend}</div>
              <div style={{ fontSize: "0.8rem", color: "#666", marginTop: "0.25rem" }}>
                Method: {hybridRun.fusion_method} (k: {hybridRun.rrf_k ?? "N/A"}, α: {hybridRun.alpha ?? "N/A"})
              </div>
            </div>
          ) : (
            <p style={{ color: "#f87171", margin: 0 }}>Run {hybrid} not found</p>
          )}
        </div>
      </section>

      {/* FILTER LINKS — each is a <Link> that sets ?filter=...; the server
          re-renders with the new searchParams. No client component, no useState.
          The active filter is brightened. */}
      <nav style={{ display: "flex", gap: "1rem", marginBottom: "1rem" }}>
        {FILTERS.map((f) => (
          <Link
            key={f}
            href={`/runs/fusion?hybrid=${hybrid}&lexical=${lexical}&vector=${vector}&filter=${f}`}
            style={{
              color: f === filter ? "#fff" : "#888",
              textDecoration: "none",
            }}
          >
            {f}
          </Link>
        ))}
      </nav>

      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.9rem" }}>
        <thead>
          <tr style={{ color: "#888" }}>
            <th style={leftCell}>query</th>
            <th style={cell}>lexical</th>
            <th style={cell}>vector</th>
            <th style={cell}>hybrid</th>
            <th style={leftCell}>category</th>
          </tr>
        </thead>
        <tbody>
         {visible.map((row) => (
            <tr key={row.query_id}>
              <td style={leftCell}>
                <Link 
                  href={`/runs/compare/${row.query_id}?a=${hybrid}&b=${vector}`} 
                  style={{ color: "#38bdf8", textDecoration: "none" }}
                >
                  {row.query_text || `ID: ${row.query_id}`}
                </Link>
              </td>
              <td style={cell}>{row.lexical_ndcg.toFixed(3)}</td>
              <td style={cell}>{row.vector_ndcg.toFixed(3)}</td>
              <td style={cell}>{row.hybrid_ndcg.toFixed(3)}</td>
              <td style={{ ...leftCell, color: categoryColor[row.category], fontWeight: "600" }}>
                {row.category}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
