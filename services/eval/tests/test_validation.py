"""Fuzz validation: our metrics vs pytrec_eval (trec_eval's C code) on
randomized rankings and qrels.

100 random queries, fixed seed (reproducible): qrels with graded judgments
including explicit 0s, rankings mixing judged/unjudged docs, lengths 1-30.
Every per-query value must match the reference within 1e-6.

Three deliberate setup decisions that keep the comparison apples-to-apples:

1. SCORES, NOT RANKS. trec_eval ignores your submitted order -- it re-sorts
   the run by score (ties broken by doc id). We assign strictly decreasing
   scores so the re-sort reproduces our intended order exactly and ties
   cannot occur. Tie handling is a real-world gotcha deferred to the BEIR
   baseline checkpoint.

2. RR IS COMPARED AT FULL DEPTH. trec_eval's recip_rank has no cutoff; ours
   takes k. We pass k = len(ranking) so the cutoff never bites. Our RR@k
   choice stands -- it just isn't what this particular measure tests.

3. EVERY QUERY HAS >= 1 RELEVANT DOC. Our zero-relevant convention
   (return 0.0) deliberately differs from trec_eval (drops the query), so
   fuzzing it against the library would only test a documented disagreement.
   The hand fixtures in test_metrics.py own that behavior.
"""

import random

import pytest
import pytrec_eval

from metrics import ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank

N_QUERIES = 100
SEED = 20260612  # fixed: a red case must be re-runnable, not a one-off ghost
KS = (5, 10)


def _random_cases() -> dict[str, tuple[list[str], dict[str, int]]]:
    rng = random.Random(SEED)
    docs = [f"d{i}" for i in range(50)]
    cases = {}
    for qi in range(N_QUERIES):
        judged = rng.sample(docs, rng.randint(3, 20))
        # Grades 0-3: explicit zeros (judged non-relevant) included on purpose.
        qrels = {doc: rng.randint(0, 3) for doc in judged}
        qrels[judged[0]] = rng.randint(1, 3)  # guarantee >= 1 relevant (see #3)
        ranking = rng.sample(docs, rng.randint(1, 30))
        cases[f"q{qi}"] = (ranking, qrels)
    return cases


CASES = _random_cases()

# Build the trec_eval-side inputs: qrels as-is, run as doc -> score with
# strictly decreasing scores encoding our ranking order (see #1).
_QREL = {qid: qrels for qid, (_, qrels) in CASES.items()}
_RUN = {
    qid: {doc: float(len(ranking) - i) for i, doc in enumerate(ranking)}
    for qid, (ranking, _) in CASES.items()
}
_MEASURES = {f"P_{k}" for k in KS} | {f"recall_{k}" for k in KS} | {
    f"ndcg_cut_{k}" for k in KS
} | {"recip_rank"}

REFERENCE = pytrec_eval.RelevanceEvaluator(_QREL, _MEASURES).evaluate(_RUN)


@pytest.mark.parametrize("qid", sorted(CASES))
class TestAgainstPytrecEval:
    def test_precision_at_k(self, qid):
        ranking, qrels = CASES[qid]
        for k in KS:
            assert precision_at_k(ranking, qrels, k) == pytest.approx(
                REFERENCE[qid][f"P_{k}"], abs=1e-6
            ), f"{qid}: P@{k} diverges"

    def test_recall_at_k(self, qid):
        ranking, qrels = CASES[qid]
        for k in KS:
            assert recall_at_k(ranking, qrels, k) == pytest.approx(
                REFERENCE[qid][f"recall_{k}"], abs=1e-6
            ), f"{qid}: recall@{k} diverges"

    def test_reciprocal_rank(self, qid):
        ranking, qrels = CASES[qid]
        # Full depth -- see header note #2.
        assert reciprocal_rank(ranking, qrels, k=len(ranking)) == pytest.approx(
            REFERENCE[qid]["recip_rank"], abs=1e-6
        ), f"{qid}: RR diverges"

    def test_ndcg_at_k(self, qid):
        ranking, qrels = CASES[qid]
        for k in KS:
            assert ndcg_at_k(ranking, qrels, k) == pytest.approx(
                REFERENCE[qid][f"ndcg_cut_{k}"], abs=1e-6
            ), f"{qid}: nDCG@{k} diverges"
