from collections import defaultdict

def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    
    if k < 0:
        raise ValueError(f"Parameter 'k' must be greater than or equal to 0. Received: {k}")

    fused_scores: dict[str, float] = defaultdict(float)

    for ranked in ranked_lists:
        for (rank, doc_id) in enumerate(ranked, start=1):
            fused_scores[doc_id] += 1 / (k + rank)

    return sorted(fused_scores.items(), key=lambda item: (-item[1], item[0]))
