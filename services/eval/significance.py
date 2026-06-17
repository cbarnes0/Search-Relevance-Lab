"""Paired significance test between two eval runs' per-query nDCG.

Answers the Task 5 honesty question: is run A's nDCG advantage over run B
real, or could it be noise from these particular queries? Reuses the stored
per-query rows (eval_results) -- no searches are re-run.

Diff is computed as A - B, so pass the *hybrid* run as A and the baseline as B.

Usage (env loaded, from services/eval):
    uv run python significance.py <run_a_id> <run_b_id>
"""

import math
import sys
from statistics import NormalDist, mean, stdev

from runner import connect


def paired_ndcg(conn, run_a: int, run_b: int) -> list[tuple[float, float]]:
    """Per-query (A_ndcg, B_ndcg) for queries present in both runs.

    The JOIN on query_id is what makes this a *paired* comparison: each query
    contributes one A and one B scored on the same information need.
    """
    rows = conn.execute(
        "SELECT a.ndcg, b.ndcg "
        "FROM eval_results a "
        "JOIN eval_results b ON a.query_id = b.query_id "
        "WHERE a.run_id = %s AND b.run_id = %s",
        (run_a, run_b),
    ).fetchall()
    return [(float(a), float(b)) for a, b in rows]


def sign_test_p(wins: int, losses: int) -> float:
    """Two-sided sign test. Under H0 (A and B equally good), each *decisive*
    query is a coin flip, so wins ~ Binomial(n, 0.5). Ties carry no signal and
    are dropped. Non-parametric: makes no assumption about the diff distribution.
    """
    n = wins + losses
    if n == 0:
        return 1.0
    extreme = max(wins, losses)
    upper_tail = sum(math.comb(n, i) for i in range(extreme, n + 1)) / 2**n
    return min(1.0, 2 * upper_tail)


def main() -> None:
    run_a, run_b = int(sys.argv[1]), int(sys.argv[2])
    with connect() as conn:
        pairs = paired_ndcg(conn, run_a, run_b)

    diffs = [a - b for a, b in pairs]
    n = len(diffs)
    wins = sum(1 for d in diffs if d > 0)
    losses = sum(1 for d in diffs if d < 0)
    ties = sum(1 for d in diffs if d == 0)

    md = mean(diffs)
    sd = stdev(diffs)
    se = sd / math.sqrt(n)
    z = md / se if se else 0.0
    # Two-sided p from the normal approximation to the paired t (n large -> CLT).
    t_p = 2 * (1 - NormalDist().cdf(abs(z)))

    print(f"A=run {run_a}  B=run {run_b}  n={n} paired queries")
    print(f"mean nDCG diff (A - B): {md:+.4f}  (sd={sd:.4f})")
    print(f"per-query: wins={wins}  losses={losses}  ties={ties}")
    print(f"sign test (two-sided):       p = {sign_test_p(wins, losses):.4g}")
    print(f"paired t, normal approx:     z = {z:.2f},  p = {t_p:.4g}")


if __name__ == "__main__":
    main()
