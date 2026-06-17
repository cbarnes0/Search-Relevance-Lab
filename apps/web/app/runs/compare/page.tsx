import Link from "next/link";

import Breadcrumbs from "../../Breadcrumbs";
import MetricsGlossary from "../../MetricsGlossary";
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
      <main className="container">
        <p className="error">
          Missing run ids. Pick two runs from the{" "}
          <Link href="/runs">runs page</Link>.
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
    <main className="container">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Runs", href: "/runs" },
          { label: `Compare ${a} vs ${b}` },
        ]}
      />
      <h1 className="page-title">
        Run {a} vs Run {b}
      </h1>
      <p className="intro">
        The two runs scored on the <strong>same queries</strong>. The cards show
        each run&apos;s average across all queries; the table below is one row per
        query. Each <strong>Δ (delta)</strong> column is run B&apos;s score minus
        run A&apos;s — <span className="delta-pos">green</span> means B did better
        on that query, <span className="delta-neg">red</span> means A did. Click a
        column header to re-sort; click a query to see both ranked lists.
      </p>

      <MetricsGlossary />

      {/* Aggregate header: the two runs' means side by side. */}
      <div className="card-grid">
        {[runA, runB].map((run, i) =>
          run === null ? (
            <div key={i} className="card error">
              Run not found
            </div>
          ) : (
            <div key={run.id} className="card">
              <h3>
                {i === 0 ? "A" : "B"}: run {run.id} · {run.backend}
              </h3>
              <div className="card__meta">
                nDCG {run.mean_ndcg.toFixed(4)} · P {run.mean_precision.toFixed(4)} ·
                recall {run.mean_recall.toFixed(4)} · MRR {run.mean_mrr.toFixed(4)}
              </div>
            </div>
          ),
        )}
      </div>

      <table>
        <thead>
          <tr>
            <th>query</th>
            {/* One sortable header per metric; the active sort is brightened. */}
            {SORT_METRICS.map((m) => (
              <th key={m} className="num">
                <Link
                  href={`/runs/compare?a=${a}&b=${b}&sort=${m}`}
                  style={{ color: m === sort ? "#fff" : "var(--text-muted)" }}
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
              <td>
                <Link href={`/runs/compare/${row.query_id}?a=${a}&b=${b}`}>
                  {row.query_text}
                </Link>
              </td>
              {/* A delta cell per metric: green if B won, red if A won. */}
              {SORT_METRICS.map((m) => {
                const d = delta(row, m);
                const cls = d > 0 ? "delta-pos" : d < 0 ? "delta-neg" : "delta-zero";
                return (
                  <td key={m} className={`num ${cls}`}>
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
