import Link from "next/link";

import type { QueryDrilldown, RankedDoc, RunSummary } from "../../../types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function getDrilldown(
  a: number,
  b: number,
  qid: string,
): Promise<QueryDrilldown | null> {
  const res = await fetch(`${API_URL}/runs/${a}/queries/${qid}/compare/${b}`, {
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

async function getRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${API_URL}/runs`, { cache: "no-store" });
  if (!res.ok) return [];
  return res.json();
}

function RankedList({ heading, docs }: { heading: string; docs: RankedDoc[] }) {
  return (
    <section style={{ flex: 1, minWidth: 0 }}>
      <h2 style={{ fontSize: "1.1rem" }}>{heading}</h2>
      {docs.length === 0 ? (
        <p style={{ color: "#888" }}>No results</p>
      ) : (
      <ol style={{ margin: 0, padding: 0 }}>
        {docs.map((doc) => {
          const relevant = doc.relevance > 0;
          return (
            <li
              key={`${doc.doc_id}-${doc.rank}`}
              style={{
                listStyle: "none",
                padding: "0.5rem 0.75rem",
                borderBottom: "1px solid #222",
                // the highlight: relevant docs get a visible treatment
                borderLeft: relevant ? "3px solid #4ade80" : "3px solid transparent",
                background: relevant ? "#14271b" : "transparent",
              }}
            >
              <div style={{ fontSize: "0.8rem", color: "#666" }}>
                #{doc.rank} · {doc.doc_id}
                {relevant ? `  ✓ rel ${doc.relevance}` : ""}
              </div>
              <div>{doc.title}</div>
            </li>
          );
        })}
      </ol>
      )}
    </section>
  );
}

export default async function DrilldownPage({
  params,
  searchParams,
}: {
  params: Promise<{ qid: string }>;
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { qid } = await params; // from the path segment [qid]
  const { a: aStr, b: bStr } = await searchParams; // from ?a=&b=
  const a = Number(aStr);
  const b = Number(bStr);

  if (!a || !b) {
    return (
      <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
        <p style={{ color: "#f87171" }}>Missing run ids in the URL.</p>
      </main>
    );
  }

  const [data, runs] = await Promise.all([getDrilldown(a, b, qid), getRuns()]);
  if (data === null) {
    return (
      <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
        <p style={{ color: "#f87171" }}>Query not found in one of the runs.</p>
      </main>
    );
  }

  const backendA = runs.find((r) => r.id === a)?.backend ?? "?";
  const backendB = runs.find((r) => r.id === b)?.backend ?? "?";

  return (
    <main style={{ padding: "2rem", maxWidth: "1100px", margin: "2rem auto" }}>
      <p style={{ marginBottom: "0.25rem" }}>
        <Link href={`/runs/compare?a=${a}&b=${b}`}>← back to comparison</Link>
      </p>
      <h1 style={{ marginBottom: "0.25rem" }}>{data.query_text}</h1>
      <p style={{ color: "#888", marginBottom: "2rem" }}>
        {data.query_id} · run {a} ({backendA}, A) vs run {b} ({backendB}, B) ·
        relevant docs highlighted
      </p>

      <div style={{ display: "flex", gap: "2.5rem", alignItems: "flex-start" }}>
        <RankedList heading={`A — run ${a} (${backendA})`} docs={data.a} />
        <RankedList heading={`B — run ${b} (${backendB})`} docs={data.b} />
      </div>
    </main>
  );
}
