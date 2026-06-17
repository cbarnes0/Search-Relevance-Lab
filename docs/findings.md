# Findings

## 2026-06-13 (sha 4124a9a)

Vector beats lexical on relevance across the board on NFCorpus.

lexical k=10: P@10=0.1390 R@10=0.0933 MRR=0.4121 nDCG@10=0.2150 mean_latency=156.8257ms n=323
vector k=10: P@10=0.2557 R@10=0.1619 MRR=0.5288 nDCG@10=0.3433 mean_latency=1276.4885ms n=323

P@10=0.14, R@10=0.09 - both low, and that is expected. NFCorpus queries have many relevant docs and lexical retrieval on a medical corpus with vocab mismatch is genuinely hard.

Vector wins every relevance metric decisively and pays ~8x in latency. This makes sense for a medical corpus where queries and documents (clinical abstracts) use different vocabulary, so lexical term-matching struggles and semantic embeddings shine. 

Latency is inflated for vector, because 8 simultaneous CPU-bound embedding encodes contending on the shared host. The true single-req latency is much lower. 

Lexical's 0.215 nDCG@10 is below the published BEIR BM25 baseline (~0.32), while vector matches its baseline — so something about our lexical setup is underperforming, to investigate at the baseline checkpoint. 

investigated below


vector is ~8× slower at the median, but lexical's latency is relatively more variable (p95 = 2× its median vs vector's 1.5×)
lexical is cheap CPU work, so its latency is dominated by network/serialization jitter - small but variable. wide relative spread

vector is dominated by the embedding encode, which is consistently expensive - a high floor but a proportionally tighter tail, every req pays the same big cost





in evaluating against a baseline, typesense kept underperforming on @nDCG. the following was discovered.
lexical underperforms BM25 baseline; tested stemming (+0.008, real but minor) and flat weights; residual gap is structural (Typesense ≠ canonical BM25, no IDF-dominant ranking).


## 2026-06-17 — Phase 4: hybrid fusion (CHECKPOINT — refine in own words at Task 7)

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

- Gain is modest (+0.013 nDCG). **Significance not yet tested** — paired per-query
  test (run 19 vs run 16) pending in Task 6.
- weighted min-max α=1.0/0.0 endpoints don't exactly reproduce the single backends
  (min-max maps worst→0, ties with missing docs; union pads the tail). Expected.
- vector/hybrid latency (~1.2 s) is inflated by concurrent CPU encodes on a shared
  host, not a true single-request cost.

### Pending (Task 6)

Per-query win/loss analysis; significance test; example queries where fusion helped
vs. hurt, with a hypothesis why.