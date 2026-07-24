# Ros_after_emSLAM — Bandwidth-Aware Constraint Scheduling (BACS)

Simulation code and reproducibility artifacts for the paper

> **Bandwidth-Aware Constraint Scheduling for Trust-Weighted Multi-Robot Map
> Fusion under Duty-Cycle-Limited Wireless Links**

Collaborative SLAM over low-power wide-area radio (LoRa, EU868) is usually framed
as a *weighting* problem: constraints arrive late or corrupted, and the fusion
back-end decides how much to believe them. Under a 1% duty-cycle ceiling a
transmitter can send only ~6 constraint packets per minute, while the mapping
front-end produces candidates ~180× faster. The binding question therefore
becomes **which candidate to spend the channel on**, not how to weight the
survivors.

**BACS** moves the trust decision from the receiver to the transmitter. Each
robot predicts the trust score its candidate would receive at the fusion server,
gates on an admissibility threshold, and ranks the admissible candidates by an
information-gain surrogate per unit airtime — solved as a knapsack within each
duty-cycle window in `O(n log n)`.

At the regulatory duty cycle, the gated scheduler reduces per-step pose RMSE by
**32.5%** relative to FIFO queueing (0.354 m vs 0.524 m; Wilcoxon W = 0,
p = 0.031).

## Repository layout

```
bacs_sim/            simulation package (module layout mirrors the manuscript)
scripts/reproduce.py CLI that regenerates the paper's experiment tables (CSV)
tests/               smoke + reproducibility tests
paper/               the full manuscript (BACS_full_paper.docx)
```

The `bacs_sim` package modules map onto the paper's sections — see
[`bacs_sim/README.md`](bacs_sim/README.md) for the file-to-section table and the
findings that revise the manuscript.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# or, to install the package itself (with test extras):
pip install -e ".[test]"
```

Requires Python ≥ 3.9 with NumPy, pandas and SciPy.

## Quick start

```python
from bacs_sim import SimConfig, run, precompute

cfg = SimConfig()
cfg.trust.gamma = 0.003           # calibrated empirical optimum (see below)
cfg.scheduler.policy = "bacs_gated"
pre = precompute(cfg)             # share world data across policies
result = run(cfg, precomputed=pre)
print(result.pose_rmse, result.trust_yield)
```

Available policies: `send_all`, `fifo`, `random`, `greedy_trust`, `greedy_info`,
`bacs`, `bacs_gated`. Each run is ~4–6 s (2 robots, 12-min session).

## Reproducing the paper

```bash
python scripts/reproduce.py                 # all scenarios, seeds 0..4 -> ./results
python scripts/reproduce.py --only s1 s5    # a subset
python scripts/reproduce.py --seeds 8       # more seeds
```

| Scenario | What it produces |
|---|---|
| `s1` | scheduling policy comparison |
| `s2` | airtime budget sweep |
| `s3` | channel robustness (delay / loss / burst) |
| `s4` | temporal decay-coefficient study (tests **H1**) |
| `s5` | utility ablation (Eq. 13) |
| `s6` | scalability across team size (tests **H3**) |

Each scenario writes one CSV into `results/`.

## Key findings

1. **Staleness is queueing, not propagation.** Under 1% duty cycle, airtime
   deferral contributes ~155 s to packet age; the 0.05–0.2 s channel delays
   commonly studied are three orders of magnitude smaller and have no measurable
   effect on accuracy.
2. **The closed-form decay coefficient (Eq. 16) is falsified (H1).** It predicts
   γ\* = 0.033; the empirical optimum is 0.003 — it anchors to the odometry-drift
   timescale when it should anchor to the airtime-queueing timescale.
3. **Multiplying trust × info gain (Eq. 13) is structurally unsound.** Predicted
   trust spans two decades while the info surrogate is bounded in [0, 1], so the
   product is trust-dominated. Use trust as an admissibility **gate** and rank by
   information density (`bacs_gated`).
4. **The advantage does not scale past three robots** (29.5% at 2 → reverses to
   −22.6% at 5); the info surrogate does not capture the coverage/observability
   tension that emerges as teams grow.

## Tests

```bash
pytest
```

## Citation

See [`CITATION.cff`](CITATION.cff). Author and venue details are withheld pending
double-anonymous review.

## License

MIT — see [`LICENSE`](LICENSE).
