import math


def relevant_ids(qrels: dict[str, int]) -> set[str]:
    """Doc ids judged relevant (grade > 0).

    Explicit grade-0 judgments ("judged non-relevant") and unjudged docs are
    both treated as non-relevant, matching pytrec_eval's binarization.
    """
    return {key for key, value in qrels.items() if value > 0}


def precision_at_k(ranked_ids: list[str], qrels: dict[str, int], k: int) -> float:
    """Fraction of the top-k results that are relevant.

    The denominator is always k, even if fewer than k results were returned
    (trec_eval convention): a short result list is a worse page, not a free pass.
    """
    top_k = ranked_ids[:k]
    relevant = relevant_ids(qrels)
    hits = sum(1 for item in top_k if item in relevant)

    return hits / k


def recall_at_k(ranked_ids: list[str], qrels: dict[str, int], k: int) -> float:
    """Fraction of all relevant docs that appear in the top-k results.

    Returns 0.0 when qrels contains no relevant docs (avoids division by zero;
    trec_eval instead drops such queries -- revisit when averaging across queries).
    """
    top_k = ranked_ids[:k]
    relevant = relevant_ids(qrels)
    relevant_qrels = len(relevant)

    if relevant_qrels == 0:
        return 0.0

    hits = sum(1 for item in top_k if item in relevant)

    return hits / relevant_qrels


def reciprocal_rank(ranked_ids: list[str], qrels: dict[str, int], k: int) -> float:
    """
    truncates at k (so RR@k, unlike trec_eval's uncutoff recip_rank),
    returns 0.0 when nothing relevant lands in the window,
    and per-query — the mean that puts the M in MRR lives in the runner
    """
    top_k = ranked_ids[:k]
    relevant = relevant_ids(qrels)

    for rank, item in enumerate(top_k, start=1):
        if item in relevant:
            return 1.0 / rank

    return 0.0


def ndcg_at_k(ranked_ids: list[str], qrels: dict[str, int], k: int) -> float:
    """Normalized discounted cumulative gain over the top-k results.

    Linear gain (gain = grade), matching the trec_eval/BEIR lineage we
    validate against -- NOT the 2^rel - 1 web-search variant. Discount is
    log2(rank + 1). The ideal ranking is the qrels grades sorted descending,
    truncated at k just like the actual ranking. Returns 0.0 when the query
    has no relevant docs (IDCG = 0).
    """
    top_k = ranked_ids[:k]
    gains = []
    for item in top_k:
        gains.append(qrels.get(item, 0))

    ideal_gains = sorted(qrels.values(), reverse=True)[:k]

    actual_dcg, idcg = dcg(gains), dcg(ideal_gains)

    if idcg == 0:
        return 0.0

    return actual_dcg / idcg


def dcg(gains: list[int]) -> float:
    """Discounted cumulative gain: sum of gain / log2(rank + 1), rank from 1."""
    return_value = 0.0
    for rank, item in enumerate(gains, start=1):
        return_value += item / math.log2(rank + 1)

    return return_value
