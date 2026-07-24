"""
Smoke tests: the simulator runs, is deterministic, and reproduces the paper's
central qualitative claim that the gated scheduler beats FIFO queueing.
"""
import math

from bacs_sim import SimConfig, run, precompute, POLICIES


def _run(policy, seed=0, gamma=0.003):
    cfg = SimConfig()
    cfg.seed = seed
    cfg.trust.gamma = gamma
    cfg.scheduler.policy = policy
    pre = precompute(cfg)
    return run(cfg, precomputed=pre)


def test_policies_registered():
    for p in ("fifo", "bacs", "bacs_gated", "send_all"):
        assert p in POLICIES


def test_run_produces_finite_metrics():
    r = _run("bacs_gated")
    assert math.isfinite(r.pose_rmse)
    assert r.pose_rmse > 0
    assert 0.0 <= r.trust_yield <= 1.0
    assert r.n_delivered > 0


def test_deterministic_under_fixed_seed():
    a = _run("bacs_gated", seed=1)
    b = _run("bacs_gated", seed=1)
    assert a.pose_rmse == b.pose_rmse
    assert a.n_delivered == b.n_delivered


def test_gated_scheduler_beats_fifo():
    """The paper's headline: BACS-gated lowers pose RMSE vs FIFO at the
    regulatory duty cycle. Check the direction of the effect."""
    gated = _run("bacs_gated")
    fifo = _run("fifo")
    assert gated.pose_rmse < fifo.pose_rmse
