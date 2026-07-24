# Frozen manuscript results

CSV outputs backing the tables and claims in the paper, committed so a reviewer
can trace **table value → CSV → code**. Regenerate any of them with
`scripts/reproduce.py` (for S1–S6) or `scripts/generate_paper_results.py` (for
the BACS+ / validation additions).

| File | Scenario | Backing claim |
|---|---|---|
| `progression.csv` | EMRMF-original → compliant FIFO → BACS → BACS+ | the research progression, one change per stage |
| `s7_surrogate_validation.csv` | Spearman ρ(Î, exact MI) by team size | surrogate fidelity, and how it degrades with N |
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
- **S7 (surrogate validation) — clear, and negative.** Spearman ρ between the
  surrogate and exact mutual information is **negative and grows more negative
  with team size** (≈ −0.36 at N = 2 → −0.66 at N = 5). The surrogate is a poor
  proxy for exact information and degrades exactly where the plain scheduler's
  advantage reverses — a quantitative account of the H3 failure.
- **Progression — BACS is the main gain.** EMRMF-original (0.387) → BACS-gated
  (0.322). Recalibrating γ alone (compliant FIFO) does not help FIFO's RMSE
  though it raises trust yield; the scheduler is where the improvement is. BACS+
  ≈ BACS at N = 2 (the observability term is meant for large teams).
- **S8 (observability across N) — inconclusive at 3 seeds.** The per-seed spread
  (std ≈ 0.07–0.10) is larger than the BACS+/BACS gap, so these runs do **not**
  establish that the observability term recovers the large-team regime. The
  machinery is in place; resolving the effect needs the 20–30 seeds of Section 7.
  Reported honestly rather than cherry-picked.
