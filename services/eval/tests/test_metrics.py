"""Hand-computable fixture tests for ranking metrics.

The fixture is small enough to verify every expected value on paper:

    qrels:  d1 -> 2   (relevant, graded high)
            d2 -> 1   (relevant)
            d3 -> 0   (judged NON-relevant -- explicit zero, must not count)
            d5 -> 1   (relevant, but never retrieved below)
    => 3 relevant docs total (grade > 0): d1, d2, d5

    ranked: [d1, d3, d2, d4, d6]   (d4, d6 are unjudged)

    rank:      1    2    3    4    5
    relevant?  yes  NO   yes  no   no
"""

import pytest

from metrics import precision_at_k, recall_at_k

QRELS = {"d1": 2, "d2": 1, "d3": 0, "d5": 1}
RANKED = ["d1", "d3", "d2", "d4", "d6"]


class TestPrecisionAtK:
    def test_k1_top_doc_relevant(self):
        # top 1 = [d1], 1 relevant / 1
        assert precision_at_k(RANKED, QRELS, k=1) == 1.0

    def test_k3_explicit_zero_grade_not_relevant(self):
        # top 3 = [d1, d3, d2]; d3 is judged 0 -> 2 relevant / 3
        assert precision_at_k(RANKED, QRELS, k=3) == pytest.approx(2 / 3)

    def test_k5_unjudged_docs_not_relevant(self):
        # top 5 = all of RANKED; d4, d6 unjudged -> 2 relevant / 5
        assert precision_at_k(RANKED, QRELS, k=5) == pytest.approx(0.4)

    def test_k_exceeds_result_count_denominator_stays_k(self):
        # Only 5 docs returned but k=10: still 2 relevant / 10, NOT 2 / 5.
        # (trec_eval convention -- a short result list is a worse page.)
        assert precision_at_k(RANKED, QRELS, k=10) == pytest.approx(0.2)

    def test_empty_results(self):
        assert precision_at_k([], QRELS, k=5) == 0.0

    def test_empty_qrels(self):
        assert precision_at_k(RANKED, {}, k=5) == 0.0


class TestRecallAtK:
    def test_k1(self):
        # top 1 = [d1]; 1 of 3 relevant docs found
        assert recall_at_k(RANKED, QRELS, k=1) == pytest.approx(1 / 3)

    def test_k3(self):
        # top 3 = [d1, d3, d2]; d1 and d2 found -> 2 / 3
        assert recall_at_k(RANKED, QRELS, k=3) == pytest.approx(2 / 3)

    def test_k5_ceiling_below_one(self):
        # d5 is relevant but was never retrieved: recall is capped at 2/3
        # no matter how deep we look in this result list.
        assert recall_at_k(RANKED, QRELS, k=5) == pytest.approx(2 / 3)

    def test_zero_relevant_docs_returns_zero(self):
        # Division-by-zero guard: no relevant docs -> 0.0 by convention.
        assert recall_at_k(RANKED, {}, k=5) == 0.0

    def test_all_grades_zero_returns_zero(self):
        # Explicit 0s only: still zero relevant docs in the denominator.
        assert recall_at_k(RANKED, {"d1": 0, "d3": 0}, k=5) == 0.0

    def test_empty_results(self):
        assert recall_at_k([], QRELS, k=5) == 0.0

    def test_monotonic_nondecreasing_in_k(self):
        # Looking deeper can only find more: recall@k never goes down as k grows.
        values = [recall_at_k(RANKED, QRELS, k=k) for k in range(1, 8)]
        assert values == sorted(values)
