import Breadcrumbs from "../../../Breadcrumbs";
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
    <section className="column">
      <h2 style={{ marginBottom: "0.75rem" }}>{heading}</h2>
      {docs.length === 0 ? (
        <p className="muted">No results</p>
      ) : (
        <ol className="result-list">
          {docs.map((doc) => {
            const relevant = doc.relevance > 0;
            return (
              <li
                key={`${doc.doc_id}-${doc.rank}`}
                className={`result-item${relevant ? " result-item--relevant" : ""}`}
              >
                <div className="result-item__meta">
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
      <main className="container">
        <p className="error">Missing run ids in the URL.</p>
      </main>
    );
  }

  const [data, runs] = await Promise.all([getDrilldown(a, b, qid), getRuns()]);
  if (data === null) {
    return (
      <main className="container">
        <p className="error">Query not found in one of the runs.</p>
      </main>
    );
  }

  const backendA = runs.find((r) => r.id === a)?.backend ?? "?";
  const backendB = runs.find((r) => r.id === b)?.backend ?? "?";

  return (
    <main className="container">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Runs", href: "/runs" },
          { label: `Compare ${a} vs ${b}`, href: `/runs/compare?a=${a}&b=${b}` },
          { label: data.query_id },
        ]}
      />
      <h1 className="page-title">{data.query_text}</h1>
      <p className="subtitle">
        {data.query_id} · run {a} ({backendA}, A) vs run {b} ({backendB}, B)
      </p>
      <p className="intro">
        The actual ranked results each run returned for this one query, in order.
        Documents the benchmark judged <strong>relevant</strong> are{" "}
        <span style={{ color: "var(--success)" }}>highlighted green</span> (with
        their relevance grade). Comparing the two columns shows <em>why</em> one
        run scored higher — which relevant docs it surfaced, and how near the top.
      </p>

      <div className="columns">
        <RankedList heading={`A — run ${a} (${backendA})`} docs={data.a} />
        <RankedList heading={`B — run ${b} (${backendB})`} docs={data.b} />
      </div>
    </main>
  );
}
