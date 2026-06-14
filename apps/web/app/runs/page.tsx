import type { RunSummary } from "../types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function getRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_URL}/runs`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

// Small formatting helpers. `num` accepts the nullable latency columns and
// renders an em-dash instead of crashing on null.
function fmt(n: number): string {
  return n.toFixed(4);
}
function fmtNullable(n: number | null): string {
  return n === null ? "—" : n.toFixed(1);
}

// Shared cell style so every <td>/<th> lines up without repeating the object.
const cell: React.CSSProperties = {
  padding: "0.4rem 0.75rem",
  borderBottom: "1px solid #222",
  textAlign: "right",
  whiteSpace: "nowrap",
};
const leftCell: React.CSSProperties = { ...cell, textAlign: "left" };

export default async function RunsPage() {
  const runs = await getRuns();

  return (
    <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
      <h1 style={{ marginBottom: "1.5rem" }}>Eval Runs</h1>

      {/* Conditional rendering: if the list is empty, show a message INSTEAD of
          the table. `cond ? <a/> : <b/>` is the JSX way to branch. */}
      {runs.length === 0 ? (
        <p style={{ color: "#888" }}>
          No runs found. Run the eval harness, then refresh.
        </p>
      ) : (
        <>
         <form method="get" action="/runs/compare" style={{ marginBottom: "1.5rem", display: "flex", gap: "1rem", alignItems: "center" }}>
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
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: "0.9rem" }}>
          <thead>
            <tr style={{ color: "#888", textAlign: "right" }}>
              <th style={leftCell}>id</th>
              <th style={leftCell}>backend</th>
              <th style={cell}>k</th>
              <th style={leftCell}>model</th>
              <th style={cell}>nDCG</th>
              <th style={cell}>P@k</th>
              <th style={cell}>recall</th>
              <th style={cell}>MRR</th>
              <th style={cell}>p50 ms</th>
              <th style={cell}>p95 ms</th>
              <th style={cell}>n</th>
            </tr>
          </thead>
          <tbody>
            {/* .map() turns each run object into a <tr>. React needs a stable
                `key` per row so it can track them across re-renders — the run
                id is unique, so it's the natural key. */}
            {runs.map((run) => (
              <tr key={run.id}>
                <td style={leftCell}>{run.id}</td>
                <td style={leftCell}>{run.backend}</td>
                <td style={cell}>{run.k}</td>
                {/* ?? "—" handles the null embedding_model on lexical runs. */}
                <td style={leftCell}>{run.embedding_model ?? "—"}</td>
                <td style={cell}>{fmt(run.mean_ndcg)}</td>
                <td style={cell}>{fmt(run.mean_precision)}</td>
                <td style={cell}>{fmt(run.mean_recall)}</td>
                <td style={cell}>{fmt(run.mean_mrr)}</td>
                <td style={cell}>{fmtNullable(run.latency_p50_ms)}</td>
                <td style={cell}>{fmtNullable(run.latency_p95_ms)}</td>
                <td style={cell}>{run.n_queries}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </>      
      )}
    </main>
  );
}
