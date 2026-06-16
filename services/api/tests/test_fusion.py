"""Hand-computable fixture tests for Reciprocal Rank Fusion.

Worked example (the one we derived on paper), k = 60, ranks 1-indexed:

    lexical: [d1, d2, d3]
    vector:  [d2, d4, d1]

    contribution = 1 / (k + rank)        (1/61=.016393, 1/62=.016129, 1/63=.015873)

    d1 = 1/61 + 1/63 = .032266     (rank 1 lexical, rank 3 vector)
    d2 = 1/62 + 1/61 = .032522     (rank 2 lexical, rank 1 vector)  <- winner
    d3 = 1/63        = .015873     (lexical only)
    d4 = 1/62        = .016129     (vector only)

    fused order: [d2, d1, d4, d3]

d2 beats d1 purely on cross-list AGREEMENT at better positions -- the whole
point of RRF. d3/d4 sink because each shows up in only one list.
"""

import pytest

from fusion import reciprocal_rank_fusion

LEXICAL = ["d1", "d2", "d3"]
VECTOR = ["d2", "d4", "d1"]


class TestReciprocalRankFusion:
    def test_agreement_doc_in_both_lists_wins(self):
        fused = reciprocal_rank_fusion([LEXICAL, VECTOR], k=60)

        # Order is the headline assertion: consensus doc d2 first, then d1.
        assert [doc_id for doc_id, _ in fused] == ["d2", "d1", "d4", "d3"]

        scores = dict(fused)
        assert scores["d2"] == pytest.approx(1 / 62 + 1 / 61)
        assert scores["d1"] == pytest.approx(1 / 61 + 1 / 63)
        # d2 edges d1 only because it sat higher in the vector list.
        assert scores["d2"] > scores["d1"]

    def test_single_list_preserves_rank_order(self):
        # One list in, one list out: RRF is order-preserving on a lone ranking
        # (1/(k+rank) is strictly decreasing in rank).
        fused = reciprocal_rank_fusion([["a", "b", "c"]], k=60)
        assert [doc_id for doc_id, _ in fused] == ["a", "b", "c"]
        assert dict(fused)["a"] == pytest.approx(1 / 61)

    def test_doc_in_one_list_contributes_once(self):
        # x and y each appear in exactly one list at rank 1 -> identical score.
        fused = dict(reciprocal_rank_fusion([["x"], ["y"]], k=60))
        assert fused["x"] == pytest.approx(1 / 61)
        assert fused["y"] == pytest.approx(1 / 61)

    def test_empty_list_among_inputs_is_ignored(self):
        # An empty ranking contributes nothing and must not crash.
        fused = reciprocal_rank_fusion([["d1"], []], k=60)
        assert fused == [("d1", pytest.approx(1 / 61))]

    def test_no_lists_returns_empty(self):
        assert reciprocal_rank_fusion([]) == []

    def test_all_lists_empty_returns_empty(self):
        assert reciprocal_rank_fusion([[], []]) == []

    def test_ties_broken_by_doc_id_ascending(self):
        # Both docs are rank 1 in their single list -> identical 1/61 score.
        # Insertion order is zebra-first, but the tiebreak must sort by doc_id,
        # putting apple first. Proves determinism, not luck of dict ordering.
        fused = reciprocal_rank_fusion([["zebra"], ["apple"]], k=60)
        assert [doc_id for doc_id, _ in fused] == ["apple", "zebra"]

    def test_negative_k_raises(self):
        with pytest.raises(ValueError):
            reciprocal_rank_fusion([["d1"]], k=-1)

    def test_k_zero_allowed_reduces_to_inverse_rank(self):
        # k=0 is legal: denominator = rank >= 1, no division by zero.
        # rank 1 -> 1/1, rank 2 -> 1/2.
        fused = dict(reciprocal_rank_fusion([["a", "b"]], k=0))
        assert fused["a"] == pytest.approx(1.0)
        assert fused["b"] == pytest.approx(0.5)

    def test_k_controls_top_rank_vs_agreement_tradeoff(self):
        # solo_top: rank 1 in ONE list.   shared: rank 4 in BOTH lists.
        #   small k -> being #1 dominates       -> solo_top wins
        #   large k -> ranks compress, two hits -> shared wins
        # This is the k knob from the concept check, made concrete.
        lists = [
            ["solo_top", "f1", "f2", "shared"],
            ["f3", "f4", "f5", "shared"],
        ]
        small = dict(reciprocal_rank_fusion(lists, k=1))
        large = dict(reciprocal_rank_fusion(lists, k=1000))

        assert small["solo_top"] > small["shared"]   # 1/2  vs 2/5
        assert large["shared"] > large["solo_top"]   # 2/1004 vs 1/1001
