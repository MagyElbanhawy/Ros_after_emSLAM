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
| `s8_observability.csv` | FIFO / BACS / BACS+ pose RMSE by team size (3 seeds) | quick-look; superseded by the 30-seed run |
| `s8_30seed_raw.csv` | 30 held-out seeds, pose + align RMSE, 4 arms | **decisive end-to-end run** (paired Wilcoxon, Cliff's δ) |
| `s7c_paired.csv` | per-seed ρ and paired Δρ test | is the observability fidelity gain per-seed consistent? |
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
- **S7-C paired (`s7c_paired.csv`) — unanimous.** Per-seed (not pooled) Δρ =
  ρ⁺ − ρ_base is positive for **every one of 40 runs** (10 seeds × N=2..5);
  one-sided Wilcoxon p = 9.8e-4 at every N (the floor for n=10). Median Δρ ≈
  +0.10 to +0.23. The observability term improves surrogate fidelity
  consistently, not on average — the airtight statistical basis for BACS+.
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
- **S8 at 30 held-out seeds (`s8_30seed_raw.csv`) — the decisive end-to-end run.**
  Seeds 10–39 (disjoint from screening), N = 2..5, FIFO / BACS-gated / BACS+
  (0.30/6 and 0.60/5), corrected deferral-γ. Two clean findings:
  - **Pose RMSE: no significant policy effect at any N** (all paired Wilcoxon
    p > 0.11). The large ±20–30% swings seen in few-seed runs — including the
    apparent H3 "reversal" — were small-sample noise. Absolute trajectory error
    is dominated by each robot's own odometry drift and is largely insensitive to
    which inter-robot constraints are scheduled.
  - **Map-alignment RMSE: the BACS family decisively beats FIFO** — the metric
    that actually measures inter-robot map-fusion consistency. N=2: +47%
    (p≈4e-8, Cliff's δ≈−0.8); N=3: +48% (p≈2e-9, δ≈−0.9); N=4: +21–25%
    (p<0.011); N=5: BACS+ (0.30/6) +28.7% (p=7e-4, δ≈−0.53), where plain
    BACS-gated drops to marginal (+17.9%, p=0.067).
  - **Observability term vs plain BACS:** no *significant* pairwise difference on
    either metric (p = 0.2–0.98). Its point estimate is best at N=5 on alignment,
    and — unlike plain BACS — BACS+ (0.30/6) keeps a *significant* alignment edge
    over FIFO at N=5, consistent with S7-C. The two BACS+ settings (0.30/6 vs
    0.60/5) are statistically indistinguishable; 0.30/6 is preferred as the
    S7-C-validated one.

  **Bottom line:** information-optimal scheduling is *not* trajectory-RMSE-optimal
  (RMSE is odometry-bound), but it *is* map-alignment-optimal — a large,
  significant fusion-consistency win. BACS+ is justified by surrogate fidelity
  (S7-C) and preserves the alignment win into the large-team regime; it does not
  claim a pose-RMSE improvement.
