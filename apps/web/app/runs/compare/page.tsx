import Link from "next/link";

import type { QueryComparison, RunSummary } from "../../types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

// The metrics we can sort by. `as const` makes this a tuple of literal strings
// so SortMetric is the union "ndcg" | "precision" | "recall" | "mrr".
const SORT_METRICS = ["ndcg", "precision", "recall", "mrr"] as const;
type SortMetric = (typeof SORT_METRICS)[number];

async function getRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_URL}/runs`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

async function getComparison(a: number, b: number): Promise<QueryComparison[]> {
  const res = await fetch(`${API_URL}/runs/${a}/compare/${b}`, {
    cache: "no-store",
  });
  if (!res.ok) return [];
  return res.json();
}

// Per-row delta for a metric: run B minus run A. Positive = B did better here.
function delta(row: QueryComparison, m: SortMetric): number {
  return row[`b_${m}`] - row[`a_${m}`];
}

const cell: React.CSSProperties = {
  padding: "0.4rem 0.75rem",
  borderBottom: "1px solid #222",
  textAlign: "right",
  whiteSpace: "nowrap",
};
const leftCell: React.CSSProperties = { ...cell, textAlign: "left" };

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string; sort?: string }>;
}) {
  const params = await searchParams;
  const a = Number(params.a);
  const b = Number(params.b);
  // Validate the sort param against the allowed set; fall back to ndcg.
  const sort: SortMetric = SORT_METRICS.includes(params.sort as SortMetric)
    ? (params.sort as SortMetric)
    : "ndcg";

  if (!a || !b) {
    return (
      <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
        <p style={{ color: "#f87171" }}>
          Missing run ids. Pick two runs from the <Link href="/runs">runs page</Link>.
        </p>
      </main>
    );
  }

  const [runs, rows] = await Promise.all([getRuns(), getComparison(a, b)]);
  const runA = runs.find((r) => r.id === a) ?? null;
  const runB = runs.find((r) => r.id === b) ?? null;

  // Server-side sort: biggest (B - A) delta first, on the chosen metric.
  // Copy before sorting — .sort() mutates, and mutating fetched data is a trap.
  const sorted = [...rows].sort((x, y) => delta(y, sort) - delta(x, sort));

  return (
    <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>
        Run {a} vs Run {b}
      </h1>
      <p style={{ color: "#888", marginBottom: "1.5rem" }}>
        Sorted by {sort} delta (B − A), largest first.{" "}
        <Link href="/runs">← all runs</Link>
      </p>

      {/* Aggregate header: the two runs' means side by side. */}
      <section style={{ display: "flex", gap: "3rem", marginBottom: "2rem" }}>
        {[runA, runB].map((run, i) =>
          run === null ? (
            <div key={i} style={{ color: "#f87171" }}>Run not found</div>
          ) : (
            <div key={run.id}>
              <h2 style={{ fontSize: "1rem", margin: "0 0 0.25rem" }}>
                {i === 0 ? "A" : "B"}: run {run.id} · {run.backend}
              </h2>
              <div style={{ color: "#aaa", fontSize: "0.9rem" }}>
                nDCG {run.mean_ndcg.toFixed(4)} · P {run.mean_precision.toFixed(4)} ·
                recall {run.mean_recall.toFixed(4)} · MRR {run.mean_mrr.toFixed(4)}
              </div>
            </div>
          ),
        )}
      </section>

      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.9rem" }}>
        <thead>
          <tr style={{ color: "#888" }}>
            <th style={leftCell}>query</th>
            {/* One sortable header per metric. Mapping SORT_METRICS keeps the
                columns and their sort links in lockstep; the active sort is
                brightened so you can see what you're sorted by. */}
            {SORT_METRICS.map((m) => (
              <th key={m} style={cell}>
                <Link
                  href={`/runs/compare?a=${a}&b=${b}&sort=${m}`}
                  style={{ color: m === sort ? "#fff" : "#888", textDecoration: "none" }}
                >
                  Δ{m}
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.query_id}>
              <td style={leftCell}>
                <Link href={`/runs/compare/${row.query_id}?a=${a}&b=${b}`}>
                  {row.query_text}
                </Link>
              </td>
              {/* A delta cell per metric: green if B won (positive), red if A won. */}
              {SORT_METRICS.map((m) => {
                const d = delta(row, m);
                const color = d > 0 ? "#4ade80" : d < 0 ? "#f87171" : "#666";
                return (
                  <td key={m} style={{ ...cell, color }}>
                    {d > 0 ? "+" : ""}
                    {d.toFixed(3)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
