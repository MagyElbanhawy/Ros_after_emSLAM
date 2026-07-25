"""
Tests for the BACS+ / research-maturity additions:
observability term, deferral-derived gamma, duty-cycle allocation, and the
surrogate-validation plumbing.
"""
import math

import numpy as np

from bacs_sim import SimConfig, run, precompute, POLICIES, PairObservability
from bacs_sim.config import LoRaConfig, TrustConfig, InfoGainConfig
from bacs_sim.lora import regulatory_budget, airtime_budget
from bacs_sim.trust import gamma_from_deferral, gamma_deferral_derived, gamma_derived
from bacs_sim.infogain import surrogate_info


def _run(policy, gamma_rule="fixed", gamma=0.003, seed=0, n=2):
    cfg = SimConfig()
    cfg.seed = seed
    cfg.world.n_robots = n
    cfg.trust.gamma = gamma
    cfg.trust.gamma_rule = gamma_rule
    cfg.scheduler.policy = policy
    pre = precompute(cfg)
    return run(cfg, precomputed=pre)


# ------------------------------------------------------------- observability
def test_pair_observability_monotone():
    o = PairObservability(n_ref=6.0)
    assert o.score(0, 1) == 1.0                       # unconstrained pair
    o.mark(0, 1)
    assert o.score(0, 1) < 1.0                         # decreases with evidence
    assert o.score(0, 1) == o.score(1, 0)              # symmetric in the pair
    prev = o.score(0, 1)
    for _ in range(20):
        o.mark(0, 1)
    assert o.score(0, 1) < prev                         # keeps decreasing
    assert o.score(2, 3) == 1.0                         # unrelated pair untouched


def test_surrogate_info_adds_observability():
    cfg = InfoGainConfig()
    base = surrogate_info(0.5, 2, 30.0, cfg, observability=0.0)
    withobs = surrogate_info(0.5, 2, 30.0, cfg, observability=1.0)
    assert math.isclose(withobs - base, cfg.w_obs, rel_tol=1e-9)


def test_bacs_plus_registered_and_runs():
    assert "bacs_plus" in POLICIES
    r = _run("bacs_plus")
    assert math.isfinite(r.pose_rmse) and r.pose_rmse > 0
    assert r.n_delivered > 0


def test_bacs_plus_beats_fifo():
    assert _run("bacs_plus").pose_rmse < _run("fifo").pose_rmse


# ------------------------------------------------------------- deferral gamma
def test_gamma_from_deferral_formula():
    cfg = TrustConfig()
    # ln2 / 155 ~ 0.00447, inside the clip range.
    assert math.isclose(gamma_from_deferral(155.0, cfg), math.log(2) / 155.0,
                        rel_tol=1e-6)
    # Zero / negative delay falls back to the configured gamma (clipped).
    assert gamma_from_deferral(0.0, cfg) > 0


def test_deferral_gamma_below_drift_gamma():
    cfg = SimConfig()
    drift = gamma_derived(cfg.world, cfg.trust)
    defer = gamma_deferral_derived(cfg.trust)
    # The corrected timescale gives an order-of-magnitude smaller coefficient.
    assert defer < drift
    assert defer < 0.01


def test_deferral_derived_recovers_near_optimum():
    """The deferral-derived rule should land near the tuned optimum (0.003),
    and well below the falsified drift derivation."""
    tuned = _run("bacs_gated", gamma_rule="fixed", gamma=0.003).pose_rmse
    defer = _run("bacs_gated", gamma_rule="deferral_derived").pose_rmse
    drift = _run("bacs_gated", gamma_rule="derived").pose_rmse
    assert defer < drift
    assert abs(defer - tuned) < 0.05


# ------------------------------------------------------------- duty cycle 1/N
def test_regulatory_vs_shared_budget():
    lora = LoRaConfig()
    W = 60.0
    reg = regulatory_budget(W, lora)
    assert math.isclose(reg, lora.duty_cycle * W, rel_tol=1e-9)
    # shared_equal (default): per-robot budget is reg / N
    assert math.isclose(airtime_budget(W, lora, 4), reg / 4, rel_tol=1e-9)
    # per_device: each robot keeps the full ceiling
    lora2 = LoRaConfig(channel_share="per_device")
    assert math.isclose(airtime_budget(W, lora2, 4), reg, rel_tol=1e-9)
    # explicit alpha overrides 1/N
    lora3 = LoRaConfig(alpha=0.5)
    assert math.isclose(airtime_budget(W, lora3, 4), 0.5 * reg, rel_tol=1e-9)


# ------------------------------------------------------------- S7 plumbing
def test_collect_graph_exposes_validation_data():
    cfg = SimConfig()
    cfg.seed = 0
    cfg.scheduler.policy = "bacs_gated"
    pre = precompute(cfg)
    r = run(cfg, precomputed=pre, collect_graph=True)
    for key in ("graph", "hessian", "delivered", "omega"):
        assert key in r.extras
    assert r.extras["hessian"] is not None


def test_s7_returns_finite_rho():
    from bacs_sim.experiments import s7_surrogate_validation
    df = s7_surrogate_validation(seeds=range(1), counts=(2,), session_s=240.0)
    # prior-based (correct baseline) and posterior (diagnostic) both reported
    assert "rho_prior_mean" in df.columns
    assert "rho_posterior_mean" in df.columns
    assert np.isfinite(df["rho_prior_mean"].iloc[0])


def test_s7c_incremental_positive_and_finite():
    """The incremental (correct) validation should be finite and, at N=2,
    positive — the base surrogate does track true information gain."""
    from bacs_sim.experiments import s7c_incremental_validation
    df = s7c_incremental_validation(seeds=range(1), counts=(2,), session_s=240.0)
    for col in ("rho_base_mean", "rho_plus_mean", "n_candidates_mean"):
        assert col in df.columns
    assert np.isfinite(df["rho_base_mean"].iloc[0])
    assert df["rho_base_mean"].iloc[0] > 0
    # observability-augmented surrogate should not correlate worse than the base
    assert df["rho_plus_mean"].iloc[0] >= df["rho_base_mean"].iloc[0] - 0.1
