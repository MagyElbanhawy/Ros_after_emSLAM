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
scripts/             reproduce.py (S1-S6) + generate_paper_results.py (BACS+ additions)
tests/               smoke + reproducibility tests
paper_results/       frozen CSVs backing the manuscript tables
ros2_ws/             reference ROS 2 scheduler node (bacs_scheduler) for deployment
hardware/            LoRa parameters + physical-experiment protocol
paper/               manuscripts: BACS_full_paper.docx (original) + BACS_revised_manuscript.{md,docx}
paper_figures/       generated manuscript figures (scripts/make_figures.py)
```

The **revised manuscript** (`paper/BACS_revised_manuscript.md` / `.docx`) is
restructured around the validated findings — deferral-derived γ (S9),
incremental surrogate validation (S7-C), and the map-alignment result (S8) — with
tables and figures generated from `paper_results/`.

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
`bacs`, `bacs_gated`, `bacs_plus`. Each run is ~4–6 s (2 robots, 12-min session).

### BACS+ (Observability-Aware BACS)

The plain scheduler's advantage reverses beyond three robots because the
information surrogate rewards coverage, not graph observability. `bacs_plus`
adds an observability term `O_ij = exp(-n_ij / n_ref)` that steers airtime toward
under-constrained robot pairs, and pairs naturally with the corrected,
deferral-derived decay coefficient:

```python
cfg = SimConfig()
cfg.scheduler.policy = "bacs_plus"       # enables the observability term
cfg.trust.gamma_rule = "deferral_derived" # gamma = ln2 / T_defer ~ 0.0045
result = run(cfg, precomputed=precompute(cfg))
```

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

The BACS+ / validation additions have their own generator, which writes frozen
CSVs into `paper_results/`:

```bash
python scripts/generate_paper_results.py   # progression, S7, S8, S9
```

| Scenario | What it measures |
|---|---|
| `progression` | EMRMF-original → compliant FIFO → BACS → BACS+ (one change per stage) |
| `s7c` | **incremental** ρ(Î / Î⁺, true information) by team size — validates the surrogate and the observability term |
| `s7` | prior- vs posterior-baseline ρ (documents the evaluation artifact) |
| `s8` | FIFO vs BACS vs BACS+ pose RMSE across N = 2..5 (noisy; not the BACS+ headline) |
| `s9` | decay-coefficient rules: drift (Eq. 16) vs deferral-derived vs adaptive |

## Deployment (ROS 2)

`ros2_ws/src/bacs_scheduler` is a reference ROS 2 node that runs the **same**
decision functions on a real EMRMF pipeline (candidates in → selected
constraints out, one selection per duty-cycle window). It is a build-ready
scaffold, not yet run on hardware; see its README and `hardware/` for the LoRa
parameters and physical-experiment protocol.

## Key findings

1. **Staleness is queueing, not propagation.** Under 1% duty cycle, airtime
   deferral contributes ~155 s to packet age; the 0.05–0.2 s channel delays
   commonly studied are three orders of magnitude smaller and have no measurable
   effect on accuracy.
2. **The closed-form decay coefficient (Eq. 16) is falsified (H1) — and
   corrected.** It predicts γ\* = 0.033; the empirical optimum is 0.003 — it
   anchors to the odometry-drift timescale when it should anchor to the
   airtime-queueing timescale. The `deferral_derived` rule (γ = ln2 / T_defer ≈
   0.0045) makes that correction and recovers near-optimal RMSE without tuning.
3. **Multiplying trust × info gain (Eq. 13) is structurally unsound.** Predicted
   trust spans two decades while the info surrogate is bounded in [0, 1], so the
   product is trust-dominated. Use trust as an admissibility **gate** and rank by
   information density (`bacs_gated`).
4. **The information surrogate is valid, and BACS+ sharpens it.** Validated
   correctly (**S7-C**: incremental information gain against the graph state at
   scheduling time, Jacobian-based, over all candidates), the surrogate
   correlates positively with true information at every team size (ρ ≈
   0.45–0.62), and the **`bacs_plus`** observability term raises that fidelity at
   every N (Δρ ≈ +0.08 to +0.19). A naive validation against the converged
   posterior inverts the sign — an evaluation artifact documented in `s7`. The
   large-N *RMSE* effect remains noisy (S8); the case for BACS+ rests on
   surrogate fidelity, not RMSE.

## Tests

```bash
pytest
```

## Citation

See [`CITATION.cff`](CITATION.cff). Author and venue details are withheld pending
double-anonymous review.

## License

MIT — see [`LICENSE`](LICENSE).
