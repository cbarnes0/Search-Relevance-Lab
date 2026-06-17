import Breadcrumbs from "../Breadcrumbs";
import MetricsGlossary from "../MetricsGlossary";
import type { RunSummary } from "../types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function getRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_URL}/runs`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

function fmt(n: number): string {
  return n.toFixed(4);
}
function fmtNullable(n: number | null): string {
  return n === null ? "—" : n.toFixed(1);
}
// Compact fusion descriptor. Single-backend runs (no fusion_method) show an
// em-dash; rrf/weighted show their tuned knob.
function fmtFusion(r: RunSummary): string {
  if (r.fusion_method === "rrf") return `rrf k=${r.rrf_k}`;
  if (r.fusion_method === "weighted") return `weighted α=${r.alpha}`;
  return "—";
}

export default async function RunsPage() {
  const runs = await getRuns();

  return (
    <main className="container">
      <Breadcrumbs items={[{ label: "Home", href: "/" }, { label: "Runs" }]} />
      <h1 className="page-title">Eval Runs</h1>
      <p className="intro">
        Each row is one <strong>evaluation run</strong> — a search backend
        (lexical, vector, or a hybrid fusion config) scored against the same 323
        benchmark queries. The columns are quality scores (higher = better) and
        response time (lower = faster). Pick two runs below to compare them
        query-by-query.
      </p>

      <MetricsGlossary />

      {runs.length === 0 ? (
        <p className="muted">No runs found. Run the eval harness, then refresh.</p>
      ) : (
        <>
          <form method="get" action="/runs/compare" className="toolbar">
            <label>
              A:{" "}
              <select name="a">
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.id} · {r.backend} (nDCG {r.mean_ndcg.toFixed(3)})
                  </option>
                ))}
              </select>
            </label>
            <label>
              B:{" "}
              <select name="b">
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.id} · {r.backend} (nDCG {r.mean_ndcg.toFixed(3)})
                  </option>
                ))}
              </select>
            </label>
            <button type="submit">Compare</button>
          </form>

          <table>
            <thead>
              <tr>
                <th>id</th>
                <th>backend</th>
                <th className="num">k</th>
                <th>model</th>
                <th>fusion</th>
                <th className="num">nDCG</th>
                <th className="num">P@k</th>
                <th className="num">recall</th>
                <th className="num">MRR</th>
                <th className="num">p50 ms</th>
                <th className="num">p95 ms</th>
                <th className="num">n</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.id}</td>
                  <td>{run.backend}</td>
                  <td className="num">{run.k}</td>
                  <td>{run.embedding_model ?? "—"}</td>
                  <td>{fmtFusion(run)}</td>
                  <td className="num">{fmt(run.mean_ndcg)}</td>
                  <td className="num">{fmt(run.mean_precision)}</td>
                  <td className="num">{fmt(run.mean_recall)}</td>
                  <td className="num">{fmt(run.mean_mrr)}</td>
                  <td className="num">{fmtNullable(run.latency_p50_ms)}</td>
                  <td className="num">{fmtNullable(run.latency_p95_ms)}</td>
                  <td className="num">{run.n_queries}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </main>
  );
}
