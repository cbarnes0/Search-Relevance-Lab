# Findings

## 2026-06-13 (sha 4124a9a)

Vector beats lexical on relevance across the board on NFCorpus.

lexical k=10: P@10=0.1390 R@10=0.0933 MRR=0.4121 nDCG@10=0.2150 mean_latency=156.8257ms n=323
vector k=10: P@10=0.2557 R@10=0.1619 MRR=0.5288 nDCG@10=0.3433 mean_latency=1276.4885ms n=323

P@10=0.14, R@10=0.09 - both low, and that is expected. NFCorpus queries have many relevant docs and lexical retrieval on a medical corpus with vocab mismatch is genuinely hard.

Vector wins every relevance metric decisively and pays ~8x in latency. This makes sense for a medical corpus where queries and documents (clinical abstracts) use different vocabulary, so lexical term-matching struggles and semantic embeddings shine. 

Latency is inflated for vector, because 8 simultaneous CPU-bound embedding encodes contending on the shared host. The true single-req latency is much lower. 

Lexical's 0.215 nDCG@10 is below the published BEIR BM25 baseline (~0.32), while vector matches its baseline — so something about our lexical setup is underperforming, to investigate at the baseline checkpoint. 




vector is ~8× slower at the median, but lexical's latency is relatively more variable (p95 = 2× its median vs vector's 1.5×)
lexical is cheap CPU work, so its latency is dominated by network/serialiation jitter - small but variable. wide relative spread

vector is dominated by the embedding encode, which is consistently expensive - a high floor but a proportianally tighter tail, every req pays the same big cost