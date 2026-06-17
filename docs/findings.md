# Findings

## 2026-06-13 (sha 4124a9a)

Vector beats lexical on relevance across the board on NFCorpus.

lexical k=10: P@10=0.1390 R@10=0.0933 MRR=0.4121 nDCG@10=0.2150 mean_latency=156.8257ms n=323
vector k=10: P@10=0.2557 R@10=0.1619 MRR=0.5288 nDCG@10=0.3433 mean_latency=1276.4885ms n=323

P@10=0.14, R@10=0.09 — both low, and that is expected. NFCorpus queries have many relevant docs (often dozens), so top-10 can't capture most of them, and lexical retrieval on a medical corpus with vocab mismatch is genuinely hard.

Vector wins every relevance metric decisively and pays ~8× in latency. This makes sense for a medical corpus where queries and documents (clinical abstracts) use different vocabulary, so lexical term-matching struggles and semantic embeddings shine.

### Latency

Latency is inflated for vector because 8 simultaneous CPU-bound embedding encodes contend on the shared host; the true single-req latency is much lower. The two backends also have different *shapes*: vector is ~8× slower at the median, but lexical's latency is proportionally more variable (p95 = 2× its median vs vector's 1.5×). Lexical is cheap CPU work, so its latency is dominated by network/serialization jitter — small but variable, a wide relative spread. Vector is dominated by the embedding encode, which is consistently expensive — a high floor but a proportionally tighter tail, since every request pays the same big cost.

### Lexical vs. the BM25 baseline

Lexical's 0.215 nDCG@10 is below the published BEIR BM25 baseline (~0.32), while vector matches its baseline — so something about our lexical setup underperforms. Investigated: enabling stemming added +0.008 (real but minor) and field weights were flat throughout, so neither explains the gap. The residual is structural — Typesense's `text_match` is not canonical Okapi BM25 (no IDF-dominant ranking), and isn't tunable away. (Stemming brings lexical to 0.224, the number used from here on.)


## 2026-06-17 — Phase 4: hybrid fusion

Two fusion methods behind `backend=hybrid`: RRF (rank-based) and weighted min-max
(score-based, `score = α·norm_lex + (1−α)·norm_vec`). Over-fetch 100/backend, fuse,
return top k=10. Tuned on NFCorpus **dev** (324 q, held out); reported on **test**
(323 q) so the headline isn't tuned on the eval set. Runs 15–20.

### Headline (all on test, n=323)

| system                              | nDCG@10 | P@10   | R@10   | MRR    |
|-------------------------------------|---------|--------|--------|--------|
| lexical                             | 0.2235  | 0.1517 | 0.0967 | 0.4112 |
| vector                              | 0.3428  | 0.2554 | 0.1618 | 0.5272 |
| hybrid weighted, default α=0.5      | 0.3412  | 0.2573 | 0.1749 | 0.5196 |
| hybrid rrf, tuned k=10              | 0.3384  | 0.2529 | 0.1711 | 0.5281 |
| **hybrid weighted, tuned α=0.3**    | **0.3557** | **0.2613** | 0.1719 | **0.5501** |

Tuned weighted hybrid beats both single backends on nDCG (+0.013 / +3.8% over
vector, +59% over lexical) and also wins P@10 and MRR.

### What the sweep showed

- **Tuning flipped the result.** Default α=0.5 hybrid *lost* to vector (0.3412 <
  0.3428). Dropping α to 0.3 (more vector weight) won (0.3557). The naive 50/50
  blend was wrong — as the asymmetric backends (strong vector, weak lexical) predict.
- **Interior optimum at α=0.3 on dev.** Curve rises from the vector end and
  collapses toward lexical; a ~70/30 vector/lexical blend is the sweet spot.
  α dev sweep: 0.0→.3278, 0.1→.3332, 0.2→.3365, **0.3→.3394**, 0.4→.3321,
  0.5→.3125, 0.6→.3054, 0.7→.3044, 0.8→.3044, 0.9→.3044, 1.0→.1926.
- **RRF never beats vector, even tuned** (best k=10 → 0.3384 < 0.3428). RRF's k
  only trades top-rank vs. agreement; it has no knob to down-weight the weak
  lexical arm. Weighted's α can. For an asymmetric pair, score-based weighting wins.
  k dev sweep: 1→.3128, **10→.3207**, 30→.3192, 60→.3189, 100→.3184, 200→.3187.

### Honest caveats

- **Significance (run 19 hybrid vs run 16 vector, paired on 323 queries):** mean
  nDCG diff +0.0130 (sd 0.0788). The effect is **narrow, not broad** — 199/323
  queries unchanged; among the rest hybrid wins 68 / loses 56. Paired t (normal
  approx) p≈0.003 (significant on the *mean*), but the sign test p≈0.32 (n.s. on
  the *win/loss count*). Reading: fusion helps a minority of queries and helps them
  **more than it hurts the ones it sets back**. The +0.013 headline is real but must
  not be sold as a broad win. (t-test normality is shaky with 62% ties; Wilcoxon
  would be the proper arbiter.)
- **Why the gain is modest = asymmetric arms.** Lexical trails the BM25 baseline
  (Phase 3 — Typesense's `text_match` isn't canonical Okapi BM25, so it lacks the
  IDF-dominant scoring), so it only rescues vector on the minority of
  exact-match/keyword queries where term matching beats embeddings. α=0.3 keeps
  vector dominant, which is what makes the wins large (lexical adds good finds) and
  the losses small (lexical can't overpower vector). A stronger lexical arm (true
  BM25) would likely broaden the gains — candidate future work, confirmable via the
  per-query win/loss view.
- weighted min-max α=1.0/0.0 endpoints don't exactly reproduce the single backends
  (min-max maps worst→0, ties with missing docs; union pads the tail). Expected.
- vector/hybrid latency (~1.2 s) is inflated by concurrent CPU encodes on a shared
  host, not a true single-request cost.

### Per-query win/loss (Task 6, 3-way: lexical vs vector vs hybrid α=0.3)

Most queries land `between` the two singles or `tied` (hybrid ≈ both). The decisive cases:

- **beat_both** (hybrid > *both* singles) cluster on short keyword / exact-term
  queries where lexical contributes signal vector lacks: grapes, cauliflower,
  chickpeas, coffee, salmon, pork, sweeteners, kidney beans, tempeh, titanium
  dioxide, phytic acid. → Confirms the hypothesis: fusion's wins come from lexical's
  exact-match strength complementing vector.
- **lost_both** (hybrid < *both* singles) cluster where both singles already scored
  high and agreed: cinnamon (0.94/0.92 → 0.86), smoking (0.91/0.91 → 0.77),
  saturated fat (0.64/0.64 → 0.57). → When both backends already nail it, fusion's
  reshuffle only displaces good docs.

Takeaway: fusion helps where the backends *disagree* and one has signal the other
misses; it hurts where they already *agree well*. Consistent with the narrow
significance result, and reinforces that a stronger lexical arm (true BM25) would
likely widen the beat_both set. That said, Typesense's `text_match` is interesting
to work with in its own right — and directly relevant to me, since I use Typesense
at work.

### Methods & reproducibility

- Tuning is honest by construction: α and k were chosen on the **dev** split
  (324 queries), final numbers reported on **test** (323). The dev and test query
  sets are disjoint in NFCorpus, so dev is a genuine held-out set.
- Every hybrid run persists its `fusion_method`, `rrf_k`/`alpha`, and git sha next
  to the metrics (`eval_runs`), so any row is reproducible. Tagged `v0.4.0`.
- RRF: `score(d) = Σ 1/(k + rank_i(d))`, k=60 default (Cormack et al. 2009),
  deterministic doc_id tiebreak. Weighted: min-max per backend, missing docs → 0.
- Both retrievers run concurrently (`asyncio.gather`) before fusing, so hybrid
  latency ≈ max(lexical, vector), not the sum — fusion is nearly free vs. vector.
- Over-fetch: 100 candidates per backend are fused before truncating to k=10, so a
  doc ranked deep by one backend but high by the other can still surface.

### Future work

- **A true BM25 lexical arm** (Pyserini / OpenSearch) — the most promising thread;
  the win/loss split suggests fusion's ceiling here is set by the weak lexical arm.
- **Wilcoxon signed-rank** as the proper significance test (the paired t-test's
  normality assumption is shaky with ~62% ties).
- Out of scope this phase, noted for later: rerankers, embedding-model swaps,
  z-score normalization (less outlier-sensitive than min-max).