#!/usr/bin/env python3
"""
Generate the frozen result CSVs for the BACS+ / validation contributions into
paper_results/. These are the numbers referenced by the manuscript additions;
S1-S6 come from scripts/reproduce.py.

    python scripts/generate_paper_results.py                 # default seeds
    python scripts/generate_paper_results.py --seeds 10      # tighter intervals

Runtime is a few minutes at the default seed counts.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bacs_sim import experiments as X

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "paper_results")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5,
                    help="seeds for the principal comparisons (default: 5)")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    n = args.seeds

    jobs = [
        ("progression", lambda: X.progression(seeds=range(n))),
        ("s9_deferral_gamma", lambda: X.s9_deferral_gamma(seeds=range(n))),
        ("s8_observability", lambda: X.s8_observability(seeds=range(max(n // 2, 2)))),
        ("s7_surrogate_validation",
         lambda: X.s7_surrogate_validation(seeds=range(max(n // 2, 2)))),
        ("s7c_incremental_validation",
         lambda: X.s7c_incremental_validation(seeds=range(max(n // 2, 2)))),
    ]
    for name, fn in jobs:
        print(f"[{name}] running...", flush=True)
        df = fn()
        path = os.path.join(args.out, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"[{name}] -> {path}")
    print("done.")


if __name__ == "__main__":
    main()
