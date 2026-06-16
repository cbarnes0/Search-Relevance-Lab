from collections import defaultdict

def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    
    if k < 0:
        raise ValueError(f"Parameter 'k' must be greater than or equal to 0. Received: {k}")

    fused_scores: dict[str, float] = defaultdict(float)

    for ranked in ranked_lists:
        for (rank, doc_id) in enumerate(ranked, start=1):
            fused_scores[doc_id] += 1 / (k + rank)

    return sorted(fused_scores.items(), key=lambda item: (-item[1], item[0]))

def min_max_normalize(scores: dict[str, float]) -> dict[str, float]:

    if not scores:
        return {}
        
    min_val = min(scores.values())
    max_val = max(scores.values())
    
    # Handle zero-variance case (#3)
    if max_val == min_val:
        return {doc_id: 1.0 for doc_id in scores}
        
    range_val = max_val - min_val
    return {doc_id: (score - min_val) / range_val for doc_id, score in scores.items()}

def weighted_fusion(
    lexical_scores: dict[str, float],
    vector_scores: dict[str, float],
    alpha: float = 0.5,
) -> list[tuple[str, float]]:
   
    # Guard against invalid alpha values to prevent extrapolation
    if not (0.0 <= alpha <= 1.0):
        raise ValueError(f"Parameter 'alpha' must be between 0.0 and 1.0. Received: {alpha}")
        
    # Normalize inputs independently
    norm_lex = min_max_normalize(lexical_scores)
    norm_vec = min_max_normalize(vector_scores)
    
    # Candidate set is the union of keys
    all_docs = set(lexical_scores.keys()) | set(vector_scores.keys())
    fused_scores = {}
    
    for doc_id in all_docs:
        # Missing docs default to 0.0 in the normalized space (#4)
        lex_val = norm_lex.get(doc_id, 0.0)
        vec_val = norm_vec.get(doc_id, 0.0)
        fused_scores[doc_id] = (alpha * lex_val) + ((1.0 - alpha) * vec_val)
        
    # Sort by (-score, doc_id) for deterministic tie-breaking
    return sorted(fused_scores.items(), key=lambda item: (-item[1], item[0]))