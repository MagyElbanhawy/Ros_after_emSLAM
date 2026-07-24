# bacs_sim — Bandwidth-Aware Constraint Scheduling simulator

Simulation backbone for Paper A (scheduling) and Paper B (adversarial reputation).
Module layout follows the manuscript so code and equations stay in sync.

| File | Paper section |
|---|---|
| `config.py` | all parameters, named after their symbols |
| `lora.py` | §3.1 airtime budget Eq.(1); §3.2 time-on-air Eqs.(2)–(4); channel emulator |
| `trust.py` | §3.3 Eqs.(5)–(6); §3.4 Eqs.(7)–(9); §3.7 Eqs.(15)–(17) |
| `infogain.py` | §3.5 Eq.(12) surrogate, Eq.(11) exact MI, rank correlation |
| `schedulers.py` | §3.6 Eqs.(13)–(14), all policies |
| `posegraph.py` | SE(2) weighted Gauss-Newton back-end (stands in for g2o) |
| `world.py` | ground truth, odometry drift, candidate generation |
| `simulator.py` | windowed loop with fused-map feedback |
| `agents.py` | honest (Paper A) + attacker hooks (Paper B) |
| `experiments.py` | S1–S6 runners, Wilcoxon |

## Quick start

```python
from bacs_sim import SimConfig, run, precompute

cfg = SimConfig()
cfg.trust.gamma = 0.003          # calibrated; see findings below
cfg.scheduler.policy = "bacs_gated"
pre = precompute(cfg)            # share world data across policies
result = run(cfg, precomputed=pre)
print(result.pose_rmse, result.trust_yield)
```

```python
from bacs_sim.experiments import s1_policy_comparison, s5_ablation, s6_scalability
s5_ablation(seeds=range(6)).to_csv("ablation.csv")
```

Runtime is roughly 4–6 s per run (2 robots, 12-min session); budget accordingly.

## Extending for Paper B

`agents.py` defines two hooks. `on_report` falsifies what a robot claims to have
seen; `on_declare` inflates the scheduling scores it reports about itself. The
second is the vector the scheduler newly creates — a robot overstating its
predicted trust or novelty captures a disproportionate share of a shared duty
cycle. Add reputation state to the server loop in `simulator.py` where
`server_trust` is called, then score detection against the `tampered` flag
already carried on every `Constraint`.

```python
cfg.agents = {1: AgentConfig(behavior="drift_injection", params={"bias": 0.15})}
```

## Findings that revise the manuscript

1. **Staleness is queueing, not propagation.** Under 1% duty cycle, airtime
   deferral contributes ~155 s to packet age; the 0.05–0.2 s channel delays
   studied in the parent framework are three orders of magnitude smaller and
   have no measurable effect. The temporal term of θ matters far more than the
   parent paper claimed, but for a different reason.
2. **Eq. (16) is falsified (H1).** It predicts γ* = 0.033; the empirical optimum
   is 0.003. The derivation matches γ to the odometry-drift timescale when it
   should be matched to the airtime-queueing timescale.
3. **Eq. (13) is structurally unsound.** θ̂ spans two decades while Î spans
   [0,1], so the product is always θ̂-dominated: the multiplicative form returns
   bit-identical results to trust-only ranking. Use θ̂ as an admissibility gate
   and rank by Î / T_air (`bacs_gated`).
4. **Ranking on θ̂ is self-confirming.** It favours constraints agreeing with the
   robot's current estimate, which carry least corrective information. Requires
   the fused map (not raw odometry) for the provisional residual of Eq. (8);
   with odometry the residual is dominated by the transmitter's own drift.
