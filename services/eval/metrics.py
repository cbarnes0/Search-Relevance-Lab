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
