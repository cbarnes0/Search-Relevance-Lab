import Link from "next/link";

import Breadcrumbs from "../../Breadcrumbs";
import type { FusionQueryRow, RunSummary } from "../../types";

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

function fusionLabel(run: RunSummary | null): string {
  if (!run) return "—";
  if (run.fusion_method === "rrf") return `rrf k=${run.rrf_k}`;
  if (run.fusion_method === "weighted") return `weighted α=${run.alpha}`;
  return run.backend;
}

function MetricCard({
  label,
  run,
  missingId,
}: {
  label: string;
  run: RunSummary | null;
  missingId: number;
}) {
  if (!run) {
    return (
      <div className="card error">
        {label}: run {missingId} not found
      </div>
    );
  }
  return (
    <div className="card">
      <h3>{label}</h3>
      <div className="card__value">{run.mean_ndcg.toFixed(4)}</div>
      <div className="card__meta">
        {run.backend} · {fusionLabel(run)}
      </div>
    </div>
  );
}

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
  const filter: Filter = FILTERS.includes(params.filter as Filter)
    ? (params.filter as Filter)
    : "all";

  const crumbs = [
    { label: "Home", href: "/" },
    { label: "Runs", href: "/runs" },
    { label: "Fusion" },
  ];

  if (!hybrid || !lexical || !vector) {
    return (
      <main className="container">
        <Breadcrumbs items={crumbs} />
        <p className="error">
          Need hybrid, lexical, and vector run ids, e.g.{" "}
          <code>?hybrid=19&lexical=15&vector=16</code>.
        </p>
      </main>
    );
  }

  const [runs, rows] = await Promise.all([
    getRuns(),
    getFusion(hybrid, lexical, vector),
  ]);

  const hybridRun = runs.find((r) => r.id === hybrid) ?? null;
  const lexicalRun = runs.find((r) => r.id === lexical) ?? null;
  const vectorRun = runs.find((r) => r.id === vector) ?? null;

  // Sort by hybrid's advantage over the better single, descending — beat_both
  // floats to the top, lost_both sinks. Copy before sorting (don't mutate).
  const sorted = [...rows].sort(
    (a, b) =>
      b.hybrid_ndcg -
      Math.max(b.lexical_ndcg, b.vector_ndcg) -
      (a.hybrid_ndcg - Math.max(a.lexical_ndcg, a.vector_ndcg)),
  );

  const visible =
    filter === "all" ? sorted : sorted.filter((row) => row.category === filter);

  return (
    <main className="container">
      <Breadcrumbs items={crumbs} />
      <h1 className="page-title">Fusion comparison</h1>
      <p className="intro">
        The core question: does hybrid retrieval
        (combining lexical + vector) beat either backend alone? The cards show each
        approach&apos;s average nDCG; the table is one row per query, with all
        three scores and a category summarising how hybrid did.
        Sorted so hybrid&apos;s biggest wins are at the top. Use the filters to
        isolate where fusion helped vs. hurt.
      </p>

      <details className="note">
        <summary>What do the categories mean?</summary>
        <div className="note__body">
          <dl>
            <dt>
              <span className="badge badge--beat_both">beat_both</span>
            </dt>
            <dd>Hybrid scored higher than both lexical and vector — fusion helped.</dd>
            <dt>
              <span className="badge badge--lost_both">lost_both</span>
            </dt>
            <dd>Hybrid scored lower than both — fusion hurt.</dd>
            <dt>
              <span className="badge badge--between">between</span>
            </dt>
            <dd>Hybrid landed between the two single backends.</dd>
            <dt>
              <span className="badge badge--tied">tied</span>
            </dt>
            <dd>Hybrid matched both (often a query where neither found anything).</dd>
          </dl>
        </div>
      </details>

      <div className="card-grid">
        <MetricCard label="Lexical" run={lexicalRun} missingId={lexical} />
        <MetricCard label="Vector" run={vectorRun} missingId={vector} />
        <MetricCard label="Hybrid" run={hybridRun} missingId={hybrid} />
      </div>

      {/* FILTER PILLS — each is a <Link> that sets ?filter=...; the server
          re-renders with the new searchParams. No client component, no useState. */}
      <nav className="pills">
        {FILTERS.map((f) => (
          <Link
            key={f}
            href={`/runs/fusion?hybrid=${hybrid}&lexical=${lexical}&vector=${vector}&filter=${f}`}
            className={`pill${f === filter ? " pill--active" : ""}`}
          >
            {f}
          </Link>
        ))}
      </nav>

      <table>
        <thead>
          <tr>
            <th>query</th>
            <th className="num">lexical</th>
            <th className="num">vector</th>
            <th className="num">hybrid</th>
            <th>category</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((row) => (
            <tr key={row.query_id}>
              <td>
                <Link href={`/runs/compare/${row.query_id}?a=${hybrid}&b=${vector}`}>
                  {row.query_text}
                </Link>
              </td>
              <td className="num">{row.lexical_ndcg.toFixed(3)}</td>
              <td className="num">{row.vector_ndcg.toFixed(3)}</td>
              <td className="num">{row.hybrid_ndcg.toFixed(3)}</td>
              <td>
                <span className={`badge badge--${row.category}`}>{row.category}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
