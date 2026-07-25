# Observability-Aware Bandwidth Scheduling for Trust-Weighted Multi-Robot Map Fusion under Duty-Cycle-Limited Wireless Links

*Author names withheld for double-anonymous review.*

> **Revision note (this draft).** This manuscript is restructured around three
> validated findings — a corrected trust-decay calibration (S9), a corrected
> validation of the information surrogate (S7-C), and an end-to-end evaluation on
> the metric that reflects map fusion (S8) — rather than the original S1–S6
> narrative. The two pre-registered failures (H1, H3) are retained as the
> motivation for the two corrections. All numbers below are reproducible from the
> `bacs_sim` package and the CSVs in `paper_results/` (`scripts/reproduce.py`,
> `scripts/run_s8_30seed.py`, `scripts/generate_paper_results.py`,
> `scripts/make_figures.py`).

---

## Abstract

Collaborative SLAM over low-power wide-area radio is usually framed as a
robustness problem: inter-robot constraints arrive late or corrupted, and the
fusion back-end decides how much to believe them. Under duty-cycle regulation the
prior question is more binding. A transmitter on the 868 MHz ISM band may occupy
the channel for at most 1% of any window, permitting roughly six 52-byte
constraint packets per minute against a front-end that generates candidates two
orders of magnitude faster. *Which* candidates are transmitted therefore governs
map quality more than how survivors are weighted on arrival.

We present Bandwidth-Aware Constraint Scheduling (BACS), which moves the trust
decision to the transmitter: each robot predicts the trust its candidate would
receive at the server, admits candidates passing a gate, and ranks the admissible
set by information gain per unit airtime, solved as a knapsack within each window.
Evaluation in a purpose-built simulator yields four results. **(1)** Under
duty-cycle compliance, packet staleness is dominated by airtime deferral (~155 s),
not channel propagation (0.05–0.2 s); a closed-form decay coefficient anchored to
odometry drift (H1) is falsified, and a coefficient anchored to the
airtime-queueing timescale, γ = ln2 / T_defer, recovers the tuned optimum without
hand-tuning. **(2)** Combining predicted trust with information gain
multiplicatively is structurally unsound; a gated formulation is required.
**(3)** The plain information surrogate is a *positive* but imperfect proxy for
exact incremental information; augmenting it with a pairwise **observability**
term (BACS+) improves its rank-correlation with exact mutual information for every
one of 40 held-out runs (p = 9.8×10⁻⁴ per team size). **(4)** On 30 held-out
seeds, per-step pose RMSE is odometry-bound and shows no significant scheduling
effect, but **map-alignment RMSE — the inter-robot fusion-consistency metric — is
17–49% lower under BACS than FIFO (p up to 10⁻⁹)**, and the observability term
uniquely preserves a significant advantage into the five-robot regime. We conclude
that information-optimal constraint scheduling is map-alignment-optimal, not
trajectory-RMSE-optimal, and we retain two falsified hypotheses because the manner
of their failure is the result.

**Keywords:** Multi-robot SLAM · Constraint scheduling · Duty-cycle regulation ·
LoRa · Information gain · Observability · Trust weighting · ROS 2

---

## 1. Introduction

A team of mobile robots mapping a shared environment must reconcile what each has
seen. Each robot maintains a local factor graph; inter-robot constraints tie the
graphs together; a back-end solves the combined nonlinear least-squares problem.
When constraints travel over a wireless link that delays or drops them, the
back-end faces a weighting problem, addressed in prior work by discounting
constraints whose geometry is implausible or whose age is large.

This paper begins from the link, not the estimator. In the EU 868 MHz band the
sub-band used for long-range telemetry restricts each transmitter to 1% channel
occupancy. A 52-byte constraint packet at spreading factor 7 occupies the channel
for 102.7 ms, so compliance permits ≈ 5.8 packets/min, while a front-end on two
robots exploring 150 m² generates candidates at several hundred per minute — an
oversupply near 180:1. Under that ratio the binding decision is not how to weight
an arriving constraint but *which* candidate to spend the channel on. A
first-in-first-out queue — the implicit policy of most implementations — transmits
whichever candidate waited longest, which is precisely the candidate that will
attract the largest temporal penalty on arrival: the system spends its scarcest
resource on the observations it is about to discount.

### 1.1 Contributions

1. **A corrected calibration of trust decay (H1 falsified → S9).** We show by
   decomposition that under duty-cycle compliance the dominant staleness term is
   airtime deferral (~155 s), not propagation (tens–hundreds of ms). A closed-form
   decay coefficient derived from platform drift over-predicts the empirical
   optimum by an order of magnitude; anchoring it to the airtime-queueing
   timescale, γ = ln2 / T_defer ≈ 0.0045, recovers near-optimal accuracy without
   tuning.
2. **A gated scheduling formulation.** Multiplying predicted trust by an
   information surrogate is structurally defective — trust spans two decades under
   exponential decay while the surrogate is bounded in [0,1], so the product is
   trust-dominated. Using trust as an admissibility gate and ranking on
   information density recovers the scheduling benefit the multiplicative form
   discards.
3. **An observability-aware surrogate, validated against exact information
   (S7-C).** The plain surrogate rewards spatial coverage but ignores whether a
   robot *pair's* relative transform is determined. We add a pairwise
   observability term and validate the surrogate correctly — against the exact
   incremental information a candidate would add to the graph at scheduling time.
   The augmented surrogate improves rank-correlation with exact information for
   every held-out run.
4. **An end-to-end evaluation that separates the metrics (S8).** On 30 held-out
   seeds we find per-step pose RMSE is odometry-bound and policy-insensitive,
   while map-alignment RMSE — the fusion-consistency metric — separates the
   policies decisively in favour of BACS, with the observability term preserving
   the advantage at the largest team sizes.

We retain two pre-registered hypotheses that failed (H1, H3). Each failure
identifies a wrong assumption whose correction is a usable result.

---

## 2. Related Work

Three literatures bear on the problem, developed with limited contact.

**Multi-robot SLAM under communication constraints.** Centralised architectures
concentrate optimisation at a server; distributed formulations push computation
onto robots; hybrid designs retain local processing and offload global
optimisation. Bandwidth has been addressed by sparse descriptor exchange,
buffering through outages, and budgeted loop-closure selection. None couples the
*selection* decision to the downstream *weighting* decision: a rule maximising
delivered constraint count implicitly assumes each delivered constraint
contributes equally, which fails under an age-discounting back-end. Airtime spent
on a constraint that will be discounted is wasted, and only a scheduler that
anticipates the discount avoids the waste.

**Information-theoretic measurement selection.** Information-based pose SLAM admits
loop closures whose expected information gain exceeds a threshold; graph
sparsification preserves the marginal information content. This supplies the right
notion of value — reduction in estimate uncertainty attributable to an edge — but
computing it requires the joint distribution held by the global optimiser, which
resides on the server. The transmitter holds only its local graph and the last
fused map, motivating a surrogate assembled from locally computable quantities,
*and the validation procedure required to justify the substitution* — the subject
of our Section 6.3.

**Adaptive parameters in robust estimation.** Robust-kernel thresholds — the
Huber transition, dynamic covariance scaling, the admissible residual and temporal
decay of trust-weighted fusion — are conventionally fixed by offline sweep. Where
a sweep reveals a well-defined optimum, it is reasonable to ask what determines its
location. Section 4.3 derives the decay coefficient from platform dynamics;
Section 6.2 reports the derivation is wrong by an order of magnitude, and why.

---

## 3. System Model

**Airtime budget.** Regulation caps each *device* at B_reg = δW (δ = 0.01). With
N robots sharing one sub-band and no channel-access coordination, collision
avoidance forces a system-level split B_i = α_i B_reg, Σα_i ≤ 1; equal sharing
gives α_i = 1/N. We keep the per-device ceiling and the coordination allocation
distinct, since conflating them mis-states the constraint.

**Time on air.** T_air(PL) follows the standard LoRa modulation model
(`bacs_sim/lora.py`, Eqs. 2–4), a step function of payload size — the property the
cost term of the scheduler exploits.

**Trust factor.** The server assigns θ_ij = max(0, 1 − (‖e_ij‖/τ_e)^p)·exp(−γ Δt),
floored, where ‖e_ij‖ is the geometric residual against the fused map and Δt the
communication age (Eq. 7).

**Predicted delay.** Before transmission the robot predicts
Δt̂ = k_defer·W + queue_air + T_air + T_retry, where k_defer is the expected number
of windows the candidate waits for airtime — the dominant term under compliance.

**Information gain.** The exact criterion I = ½ log det(I + Ω Σ_ij) requires the
marginal covariance Σ_ij of the relative pose, available only at the server. The
transmitter computes the surrogate Î (Section 4.2).

---

## 4. Method: Observability-Aware BACS

### 4.1 Gated information-density scheduling

Within each window the scheduler solves

    S* = argmax_S  Σ_{c∈S} Î_c / T_air,c
         subject to  θ̂_c ≥ θ_gate  and  Σ_{c∈S} T_air,c ≤ B_i,

by density-greedy knapsack with a single-best-item guard (a ½-approximation in
O(n log n); near-optimal here because constraints are small relative to the
window). Predicted trust θ̂ is an *admissibility gate*, not a ranking key: ranking
on θ̂ is self-confirming, favouring constraints that agree with the robot's current
estimate and therefore carry least corrective information. The multiplicative form
Î·θ̂ is dominated by θ̂ (two decades vs [0,1]) and reproduces trust-only ranking.

### 4.2 The information surrogate and its observability term

The base surrogate combines coverage novelty ν, normalised node degree, and loop
length:

    Î = w_ν·ν + w_d·(1 − d̄) + w_l·l̄.

This rewards *spatial coverage* but never asks whether a robot pair (i, j) has
enough constraints to determine its relative transform. We add a pairwise
**observability** term

    O_ij = exp(−n_ij / n_ref),        Î⁺ = Î + w_o·O_ij,

where n_ij is the number of inter-robot constraints already delivered for the
pair. O_ij is 1 when the pair's transform is undetermined and decays as
constraints accumulate, biasing airtime toward under-constrained pairs. We call
the resulting method **observability-aware BACS**; the base method is an
intermediate ablation.

### 4.3 Trust-decay calibration

The parent framework's derivation matches γ to the time for odometry divergence to
reach τ_e, giving γ* = ln2·σ_d·v̄/τ_e = 0.033 (Eq. 16). Under duty-cycle
compliance this is the wrong timescale. Anchoring instead to the airtime-queueing
time T_defer,

    γ_defer = ln2 / T_defer ≈ ln2 / 155 s ≈ 0.0045,

matches the empirical optimum. We evaluate five rules in Section 6.2.

---

## 5. Evaluation Platform and Hypotheses

The simulator reproduces the sensing, radio, and pose-graph pipeline of a
trust-weighted fusion framework: boustrophedon coverage with overlapping
territories, distance-scaled odometry drift, a LoRa airtime/channel model, a
two-population candidate stream (inliers < 0.35 m, outliers > 0.7 m), and an SE(2)
weighted Gauss–Newton back-end that ingests delivered constraints, re-optimises,
and republishes the fused map. We report per-step **pose RMSE** (each robot's
trajectory vs ground truth) and **map-alignment RMSE** (discrepancy between two
robots' estimates of ground-truth co-location pairs — the fusion-consistency
metric).

Pre-registered hypotheses:

- **H1.** The closed-form γ* (Eq. 16) predicts the empirical optimum. *(Falsified.)*
- **H2.** A gated formulation outperforms the multiplicative one. *(Supported.)*
- **H3.** The scheduling advantage grows with team size. *(Falsified for pose
  RMSE; reframed via observability and map alignment.)*
- **H3b (new).** Adding an observability term improves the surrogate's fidelity to
  exact incremental information. *(Supported, S7-C.)*

---

## 6. Results

### 6.1 Methodological progression

Table 1 traces one change per stage on identical worlds (5 seeds, N = 2).

**Table 1. Progression (5 seeds, N = 2).**

| Stage | pose RMSE [m] | align RMSE [m] | trust yield |
|---|---|---|---|
| EMRMF-original (FIFO, drift γ) | 0.387 | 0.34 | 0.22 |
| + compliant FIFO (deferral γ) | 0.389 | — | 0.37 |
| BACS (gated) | 0.322 | — | 0.31 |
| BACS+ (observability) | 0.329 | — | 0.30 |

Recalibrating γ raises trust yield but not FIFO's RMSE; the scheduler is where the
RMSE improvement is (Fig. 4). At N = 2 the observability term is neutral on RMSE —
its role is at larger teams and on map alignment (Section 6.4).

### 6.2 H1: trust-decay calibration (S9)

**Table 2. Decay-coefficient rules (`s9_deferral_gamma.csv`, 5 seeds, N = 2).**

| Rule | γ | pose RMSE [m] |
|---|---|---|
| fixed (tuned optimum) | 0.0030 | 0.325 |
| drift-derived (Eq. 16) | 0.0333 | 0.425 |
| drift-adaptive | 0.064 | 0.424 |
| **deferral-derived** | **0.0045** | **0.322** |
| deferral-adaptive | 1.86 | 0.384 |

The drift derivation (Eq. 16) is falsified — it over-predicts γ by ~10× and
inflates RMSE by ~30%. The deferral-derived rule reaches the tuned optimum with no
sweep (Fig. 3). The online deferral-adaptive variant overshoots because it measures
the delay of *delivered* (fresh) packets, not the queue-wide deferral; we report it
as an instructive negative.

### 6.3 H3b: surrogate validation against exact information (S7-C)

Validating the surrogate requires the *right* quantity. Scoring an edge against
the converged posterior covariance measures "how informative is this edge *after*
the graph already contains it," which inverts the ranking (edges in well-solved
regions look uninformative) and produces a spurious strong negative correlation.
The scheduling-relevant quantity is the **incremental** gain against the graph
state *before* the candidate:

    I_c = ½ log det( I + Ω_c J_c Σ_ij,t J_cᵀ ),

with Σ_ij,t the joint marginal in the graph containing odometry plus everything
delivered before window t, and J_c the SE(2) relative-pose Jacobian at the current
linearisation. We compute this over *all* candidates presented (not only
delivered, to avoid selection bias) and correlate it with the surrogate.

**Table 3. Incremental surrogate fidelity (`s7c_paired.csv`, 10 seeds/N).**

| N | ρ(Î base) | ρ(Î⁺ observability) | Δρ (median) | seeds Δρ>0 | p (one-sided) |
|---|---|---|---|---|---|
| 2 | 0.45 ± 0.13 | 0.62 ± 0.08 | +0.17 | 10/10 | 9.8×10⁻⁴ |
| 3 | 0.38 ± 0.20 | 0.61 ± 0.13 | +0.23 | 10/10 | 9.8×10⁻⁴ |
| 4 | 0.42 ± 0.11 | 0.55 ± 0.08 | +0.13 | 10/10 | 9.8×10⁻⁴ |
| 5 | 0.49 ± 0.11 | 0.60 ± 0.08 | +0.11 | 10/10 | 9.8×10⁻⁴ |

The base surrogate is a *positive* proxy for exact incremental information at every
team size (ρ ≈ 0.4–0.6); the observability term raises fidelity for **every one of
40 runs** (Fig. 1). For contrast, the posterior-baseline evaluation returns
ρ ≈ −0.4 to −0.6 — an evaluation artifact we document rather than a property of the
surrogate (`s7_surrogate_validation.csv`, posterior column).

### 6.4 H3 / end-to-end evaluation (S8, 30 held-out seeds)

**Table 4. S8 map-alignment RMSE, primary metric (`s8_30seed_summary.csv`;
seeds 10–39; mean [95% CI]).** Improvement and significance are vs FIFO
(paired Wilcoxon, Cliff's δ).

| N | FIFO | BACS | BACS+ | BACS vs FIFO | BACS+ vs FIFO |
|---|---|---|---|---|---|
| 2 | 0.334 | 0.175 | 0.180 | +47.6% (p=4e-9, δ=−0.82) | +46.0% (p=5e-8, δ=−0.79) |
| 3 | 0.436 | 0.222 | 0.227 | +49.1% (p=4e-9, δ=−0.92) | +48.1% (p=2e-9, δ=−0.90) |
| 4 | 0.276 | 0.207 | 0.217 | +25.2% (p=1e-3, δ=−0.42) | +21.3% (p=0.011, δ=−0.32) |
| 5 | 0.257 | 0.211 | **0.183** | +17.9% (p=0.067, n.s.) | **+28.7% (p=7e-4, δ=−0.53)** |

**Table 5. S8 per-step pose RMSE, secondary metric.** No arm differs significantly
from any other at any N (all paired Wilcoxon p > 0.11).

| N | FIFO | BACS | BACS+ |
|---|---|---|---|
| 2 | 0.442 | 0.378 | 0.391 |
| 3 | 0.432 | 0.399 | 0.395 |
| 4 | 0.372 | 0.376 | 0.370 |
| 5 | 0.310 | 0.337 | 0.346 |

Two findings (Fig. 2). First, **pose RMSE carries no significant policy effect**:
each robot's absolute trajectory error is dominated by its own odometry drift,
which inter-robot scheduling cannot correct. The dramatic per-team-size reversals
reported from few-seed runs (the original H3 evidence) do not survive 30 seeds —
they were small-sample noise. Second, **map-alignment RMSE separates the policies
decisively**: the BACS family lowers fusion inconsistency by 18–49% with large
effect sizes at small teams, and at N = 5 the observability term uniquely preserves
a *significant* advantage over FIFO (+28.7%, p = 7×10⁻⁴) where plain BACS becomes
marginal. The two BACS+ weight settings tested (w_o = 0.30/n_ref = 6 and
0.60/5) are statistically indistinguishable; we adopt 0.30/6, the S7-C-validated
setting.

### 6.5 Figures

![**Fig. 1.** Incremental surrogate fidelity (S7-C): Spearman ρ between the
transmitter-side surrogate and exact incremental information gain, base (Î) vs
observability-augmented (Î⁺), by team size. Δρ > 0 for all 40 runs.](../paper_figures/fig_s7c_fidelity.png)

![**Fig. 2.** S8 on 30 held-out seeds. Left (primary): map-alignment RMSE with
95% CI; ∗ marks BACS+ significantly below FIFO. Right (secondary): per-step pose
RMSE, no significant policy effect.](../paper_figures/fig_s8_alignment_vs_pose.png)

![**Fig. 3.** S9 decay-coefficient rules. The deferral-derived γ recovers the
tuned optimum (dashed) while the drift derivation of Eq. (16) is
falsified.](../paper_figures/fig_s9_gamma.png)

![**Fig. 4.** Methodological progression EMRMF-original → BACS+ on both pose and
map-alignment RMSE.](../paper_figures/fig_progression.png)

---

## 7. Discussion and Threats to Validity

**Information-optimal ≠ RMSE-optimal, but = alignment-optimal.** The central
lesson is that better information-ranking (S7-C) does not translate into lower
per-step pose RMSE, because RMSE is odometry-bound; it translates into lower
map-alignment error, which is precisely what inter-robot constraints govern. A
scheduler for *trajectory* accuracy would need a term tied to each robot's own
estimation geometry, not only to inter-robot information.

**Scope of the observability claim.** BACS+ is justified by a robust, unanimous
improvement in surrogate fidelity (S7-C) and by a uniquely significant N = 5
alignment advantage; it is *not* claimed to beat plain BACS in a direct paired
alignment test (differences there are not significant at 30 seeds). We state this
plainly.

**Overfitting.** The observability weights were screened on the same synthetic
world used for evaluation; the S7-C validation mitigates this by showing the term
tracks exact information rather than a generator artifact, but hardware validation
(Section 8) remains necessary.

**Simulation fidelity.** The pose-graph back-end stands in for g2o/GTSAM; the LoRa
model is closed-form. `bacs_sim/model.py` is a separate communication-layer
reference and is not on the path that produces any reported metric.

---

## 8. Conclusion and Future Work

Under duty-cycle regulation, the decision that governs collaborative map quality is
which constraints to transmit, not how to weight them on arrival. BACS moves that
decision to the transmitter; observability-aware BACS corrects the information
objective so it accounts for pairwise graph structure. We report a corrected decay
calibration that recovers the optimum from first principles, a corrected surrogate
validation showing the observability term improves fidelity to exact information
for every held-out run, and an end-to-end study showing the benefit is a large,
significant reduction in map-alignment error rather than in odometry-bound pose
RMSE. A reference ROS 2 node (`ros2_ws/src/bacs_scheduler`) wraps the identical
decision functions for deployment; the hardware protocol in `hardware/` specifies
the physical validation — a motion-capture-referenced, ≥ 20-session comparison over
a real RYLR998 link — that would confirm these findings outside simulation.

---

## Reproducibility

All results derive from the `bacs_sim` package and the frozen CSVs in
`paper_results/`:

| Result | Script | Output |
|---|---|---|
| Progression (Table 1, Fig. 4) | `experiments.progression` | `progression.csv` |
| γ rules (Table 2, Fig. 3) | `experiments.s9_deferral_gamma` | `s9_deferral_gamma.csv` |
| Surrogate fidelity (Table 3, Fig. 1) | `experiments.s7c_paired` | `s7c_paired.csv` |
| S8 alignment/pose (Tables 4–5, Fig. 2) | `scripts/run_s8_30seed.py` | `s8_30seed_{raw,summary,tests}.csv` |
| Figures | `scripts/make_figures.py` | `paper_figures/*.png` |

Pre-registered hypotheses and their outcomes are stated in Section 5; the two
falsified hypotheses (H1, H3) are retained deliberately.
