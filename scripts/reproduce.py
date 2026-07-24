#!/usr/bin/env python3
"""
Reproduce the experiments reported in the BACS paper.

Each scenario writes a CSV into the output directory (default: ./results).

    python scripts/reproduce.py                 # run every scenario, default seeds
    python scripts/reproduce.py --only s1 s5    # run a subset
    python scripts/reproduce.py --seeds 8       # use seeds range(8)
    python scripts/reproduce.py --out results   # choose output directory

Scenarios (see bacs_sim/experiments.py):
    s1  scheduling policy comparison
    s2  airtime budget sweep
    s3  channel robustness
    s4  decay-coefficient study (tests H1)
    s5  utility ablation
    s6  scalability (tests H3)

Runtime is roughly 4-6 s per simulator run; the full suite takes a few minutes.
"""
import argparse
import os
import sys

# Allow running as `python scripts/reproduce.py` from the repo root without
# needing an editable install.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bacs_sim import experiments as X


SCENARIOS = {
    "s1": ("policy_comparison", lambda seeds: X.s1_policy_comparison(seeds=seeds)),
    "s2": ("budget_sweep",      lambda seeds: X.s2_budget_sweep(seeds=seeds)),
    "s3": ("channel",           lambda seeds: X.s3_channel(seeds=seeds)),
    "s4": ("gamma",             lambda seeds: X.s4_gamma(seeds=seeds)),
    "s5": ("ablation",          lambda seeds: X.s5_ablation(seeds=seeds)),
    "s6": ("scalability",       lambda seeds: X.s6_scalability(seeds=seeds)),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="+", choices=sorted(SCENARIOS),
                    help="run only these scenarios (default: all)")
    ap.add_argument("--seeds", type=int, default=5,
                    help="number of seeds, i.e. range(N) (default: 5)")
    ap.add_argument("--out", default="results", help="output directory")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    seeds = range(args.seeds)
    chosen = args.only or sorted(SCENARIOS)

    for key in chosen:
        name, fn = SCENARIOS[key]
        print(f"[{key}] running {name} over {args.seeds} seed(s)...", flush=True)
        df = fn(seeds)
        path = os.path.join(args.out, f"{key}_{name}.csv")
        df.to_csv(path, index=False)
        print(f"[{key}] -> {path}")

    print("done.")


if __name__ == "__main__":
    main()
