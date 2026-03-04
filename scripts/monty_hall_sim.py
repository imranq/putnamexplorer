#!/usr/bin/env python3
"""Monte Carlo simulation for the Monty Hall problem.

Game:
- 3 boxes, 1 contains $1000.
- Player picks one box.
- Host opens an empty box among the two unpicked boxes.
- Player can stay or switch to the other unopened box.

This script estimates win probabilities and expected value under different strategies.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from typing import Dict

PRIZE = 1000.0


@dataclass
class Result:
    wins: int
    trials: int

    @property
    def win_rate(self) -> float:
        return self.wins / self.trials if self.trials else 0.0

    @property
    def fair_entry_fee(self) -> float:
        return self.win_rate * PRIZE


def run_trial(rng: random.Random, strategy: str) -> bool:
    """Return True if player wins under the given strategy.

    strategy options:
    - 'switch': always switch after host opens an empty box
    - 'stay': never switch
    - 'random': switch with probability 0.5
    """
    boxes = [0, 1, 2]
    prize_box = rng.choice(boxes)
    initial_choice = rng.choice(boxes)

    # Host opens an empty box that is not the player's current choice.
    host_options = [b for b in boxes if b != initial_choice and b != prize_box]
    host_opens = rng.choice(host_options)

    remaining_unopened = [b for b in boxes if b not in (initial_choice, host_opens)][0]

    if strategy == "switch":
        final_choice = remaining_unopened
    elif strategy == "stay":
        final_choice = initial_choice
    elif strategy == "random":
        final_choice = remaining_unopened if rng.random() < 0.5 else initial_choice
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    return final_choice == prize_box


def simulate(trials: int, seed: int | None = None) -> Dict[str, Result]:
    rng = random.Random(seed)
    results: Dict[str, Result] = {}

    for strategy in ("stay", "switch", "random"):
        wins = sum(1 for _ in range(trials) if run_trial(rng, strategy))
        results[strategy] = Result(wins=wins, trials=trials)

    return results


def pretty_strategy_name(strategy: str) -> str:
    return {
        "stay": "Never switch",
        "switch": "Always switch",
        "random": "Random (50/50)",
    }[strategy]


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate the Monty Hall box game.")
    parser.add_argument(
        "-n",
        "--trials",
        type=int,
        default=100_000,
        help="Number of trials per strategy (default: 100000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducible runs",
    )
    args = parser.parse_args()

    if args.trials <= 0:
        raise SystemExit("Trials must be a positive integer.")

    results = simulate(trials=args.trials, seed=args.seed)

    print(f"Monty Hall simulation ({args.trials:,} trials per strategy)")
    print(f"Prize amount: ${PRIZE:,.2f}\n")

    for strategy in ("stay", "switch", "random"):
        result = results[strategy]
        print(f"{pretty_strategy_name(strategy)}")
        print(f"  Wins: {result.wins:,}/{result.trials:,}")
        print(f"  Win rate: {result.win_rate:.4%}")
        print(f"  Fair entry fee: ${result.fair_entry_fee:,.2f}\n")

    print("Theory check:")
    print("  - Never switch: 1/3 win chance -> fair fee $333.33")
    print("  - Always switch: 2/3 win chance -> fair fee $666.67")


if __name__ == "__main__":
    main()
