// Plain-language glossary of the eval metrics, as a native <details> element —
// expand/collapse with zero JS, so it stays a server component. Reused on the
// runs list and comparison pages.

export default function MetricsGlossary() {
  return (
    <details className="note">
      <summary>What do these scores mean?</summary>
      <div className="note__body">
        <p>
          Each backend is scored against NFCorpus — a benchmark of 323 medical
          search queries, where humans have judged which documents are actually
          relevant to each query. Every quality score runs 0–1 and{" "}
          <strong>higher is better</strong>; for latency, lower is better.
        </p>
        <dl>
          <dt>nDCG@10</dt>
          <dd>
            Overall quality of the top-10 ranking — it rewards putting
            more-relevant documents nearer the top. This is the headline metric.
          </dd>
          <dt>precision@10 (P@k)</dt>
          <dd>Of the 10 results shown, the fraction that are relevant.</dd>
          <dt>recall@10</dt>
          <dd>
            Of all the relevant documents that exist for a query, the fraction
            that made it into the top 10.
          </dd>
          <dt>MRR</dt>
          <dd>
            How high the first relevant result lands, on average (1.0 = always at
            rank 1).
          </dd>
          <dt>p50 / p95 ms</dt>
          <dd>
            Response time: the median (p50) and the slow-tail 95th percentile
            (p95), in milliseconds.
          </dd>
        </dl>
      </div>
    </details>
  );
}
