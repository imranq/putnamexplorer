#!/usr/bin/env python3
"""Benchmark birthday paradox theoretical probability methods.

Compares:
1) Product loop for P(no collision)
2) log-gamma closed form
"""

from __future__ import annotations

import argparse
import math
import time
from typing import Iterable


DAYS_IN_YEAR = 365


def theoretical_loop(k: int, n: int = DAYS_IN_YEAR) -> float:
    if k <= 1:
        return 0.0
    if k > n:
        return 1.0

    p_no_collision = 1.0
    for i in range(k):
        p_no_collision *= (n - i) / n
    return 1.0 - p_no_collision


def theoretical_lgamma(k: int, n: int = DAYS_IN_YEAR) -> float:
    if k <= 1:
        return 0.0
    if k > n:
        return 1.0

    log_p_no_collision = math.lgamma(n + 1) - math.lgamma(n - k + 1) - k * math.log(n)
    return 1.0 - math.exp(log_p_no_collision)


def time_method(func, k_values: Iterable[int], repeats: int, n: int) -> tuple[float, dict[int, float]]:
    last_results: dict[int, float] = {}
    start = time.perf_counter()
    for _ in range(repeats):
        for k in k_values:
            last_results[k] = func(k, n)
    elapsed = time.perf_counter() - start
    return elapsed, last_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare loop vs log-gamma theoretical birthday probabilities")
    parser.add_argument("--n", type=int, default=DAYS_IN_YEAR, help="Number of possible birthdays (default: 365)")
    parser.add_argument(
        "--k-values",
        type=int,
        nargs="+",
        default=[1, 2, 5, 10, 23, 30, 50, 100, 200, 300, 365],
        help="Group sizes to compare",
    )
    parser.add_argument("--repeats", type=int, default=50_000, help="How many repeated benchmark passes")
    args = parser.parse_args()

    if args.n <= 0:
        raise SystemExit("--n must be positive")
    if args.repeats <= 0:
        raise SystemExit("--repeats must be positive")

    k_values = args.k_values

    loop_time, loop_results = time_method(theoretical_loop, k_values, args.repeats, args.n)
    lgamma_time, lgamma_results = time_method(theoretical_lgamma, k_values, args.repeats, args.n)

    print("Birthday Theoretical Probability Benchmark")
    print(f"n={args.n}, k-values={k_values}, repeats={args.repeats}")
    print()
    print(f"Loop time:   {loop_time:.6f} s")
    print(f"lgamma time: {lgamma_time:.6f} s")
    print(f"Speedup:     {loop_time / lgamma_time:.2f}x (loop/lgamma)")
    print()
    print("Per-k comparison (last computed values):")
    for k in k_values:
        loop_val = loop_results[k]
        lgamma_val = lgamma_results[k]
        abs_diff = abs(loop_val - lgamma_val)
        print(
            f"k={k:>3} | loop={loop_val:.12f} | lgamma={lgamma_val:.12f} | abs_diff={abs_diff:.3e}"
        )


if __name__ == "__main__":
    main()
