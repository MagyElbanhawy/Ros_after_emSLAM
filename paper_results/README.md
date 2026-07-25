# Frozen manuscript results

CSV outputs backing the tables and claims in the paper, committed so a reviewer
can trace **table value → CSV → code**. Regenerate any of them with
`scripts/reproduce.py` (for S1–S6) or `scripts/generate_paper_results.py` (for
the BACS+ / validation additions).

| File | Scenario | Backing claim |
|---|---|---|
| `progression.csv` | EMRMF-original → compliant FIFO → BACS → BACS+ | the research progression, one change per stage |
| `s7c_incremental_validation.csv` | Spearman ρ(Î, incremental MI) and ρ(Î⁺, ·) by team size | **the correct validation**: surrogate fidelity and the observability gain |
| `s7_surrogate_validation.csv` | ρ against odometry-prior (correct) vs converged-posterior (diagnostic) | shows the baseline artifact that inverted the original ρ |
| `s8_observability.csv` | FIFO / BACS / BACS+ pose RMSE by team size | whether the observability term helps large teams |
| `s9_deferral_gamma.csv` | decay-coefficient rules | deferral-derived γ recovers the empirical optimum |

Each CSV reports mean and standard deviation over the seed set noted in the
`seeds` column of the generation script. Column suffixes `_mean` / `_std` are
the aggregation over seeds. These are frozen at the seed counts used here
(progression/S9: 5 seeds; S7/S8: 3 seeds); increase them in the generation
script for tighter intervals — Section 7 recommends 20–30 seeds for the
principal comparisons.

## What these runs show (at the committed seed counts)

- **S9 (γ rules) — clear.** The deferral-derived rule (γ ≈ 0.0045) reaches
  pose RMSE ≈ 0.322, matching the hand-tuned optimum (0.325 at γ = 0.003) and
  well below the drift derivation of Eq. (16) (γ = 0.033 → 0.425). The corrected
  timescale recovers the optimum without tuning.
- **S7-C (incremental validation) — clear, positive, and the justification for
  BACS+.** Computed correctly — incremental information gain against the graph
  state *at the window each candidate is presented*, with the SE(2) Jacobian,
  over *all* candidates — the base surrogate correlates **positively** with true
  information at every team size (ρ ≈ 0.45–0.62, 5 seeds), and the
  observability-augmented surrogate is **higher at every N** (Δρ ≈ +0.08 to
  +0.19, with lower variance). BACS+ improves the fidelity of the
  transmitter-side approximation to true graph information — a principled reason
  for the observability term, independent of RMSE.
- **The original ρ was an evaluation artifact.** `s7_surrogate_validation.csv`
  documents it: scoring against the *converged posterior* (which already
  contains each edge and its neighbours) gives strongly negative ρ (≈ −0.4 to
  −0.6); switching the baseline to the odometry prior already flips the sign for
  N ≥ 3. The incremental S7-C is the definitive version. Do **not** read the
  posterior column as evidence about the surrogate — it measures the wrong
  quantity.
- **Progression — BACS is the main RMSE gain.** EMRMF-original (0.387) →
  BACS-gated (0.322). Recalibrating γ alone (compliant FIFO) does not help
  FIFO's RMSE though it raises trust yield; the scheduler is where the
  improvement is. BACS+ ≈ BACS on RMSE at N = 2.
- **S8 (observability RMSE across N) — not the headline; noisy at low seeds.**
  The per-seed spread (std ≈ 0.07–0.16) exceeds the BACS+/BACS RMSE gap, so these
  runs do **not** by themselves establish that the term lowers RMSE at large N.
  The case for BACS+ rests on S7-C (surrogate fidelity), not on S8. Resolving any
  RMSE effect needs the 20–30 seeds of Section 7.
