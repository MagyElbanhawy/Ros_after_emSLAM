"""
Scenario runners.  Each returns a pandas DataFrame ready for the manuscript.

S1  scheduling policy comparison
S2  airtime budget sweep
S3  channel robustness
S4  decay coefficient study (tests H1)
S5  utility ablation
S6  scalability (tests H3)
"""
import numpy as np
import pandas as pd
from dataclasses import replace

from .config import SimConfig
from .simulator import run, precompute
from .trust import gamma_derived
from .schedulers import POLICIES


def _mk(seed=0, n_robots=2, **over):
    c = SimConfig()
    c.seed = seed
    c.world.n_robots = n_robots
    for k, v in over.items():
        obj, attr = k.split(".", 1)
        setattr(getattr(c, obj), attr, v)
    return c


def _agg(records, by):
    df = pd.DataFrame(records)
    g = df.groupby(by).agg(["mean", "std"])
    g.columns = [f"{a}_{b}" for a, b in g.columns]
    return g.reset_index()


def _sweep(configs, seeds, n_robots=2, label_fn=None):
    """Run every config across every seed on shared world data."""
    recs = []
    for s in seeds:
        base = _mk(seed=s, n_robots=n_robots)
        pre = precompute(base)
        for cfg in configs:
            c = replace(cfg)
            c.seed = s
            c.world.n_robots = n_robots
            r = run(c, precomputed=pre)
            rec = dict(seed=s, pose_rmse=r.pose_rmse, align_rmse=r.align_rmse,
                       trust_yield=r.trust_yield, accept_rate=r.accept_rate,
                       airtime_util=r.airtime_util, n_delivered=r.n_delivered,
                       bytes_sent=r.bytes_sent, starvation=r.starvation,
                       sched_ms=r.sched_overhead_ms, outlier_share=r.outlier_share,
                       gamma=r.gamma_final, dt_bias=r.dt_pred_bias)
            rec.update(label_fn(cfg) if label_fn else {})
            recs.append(rec)
    return recs


# ------------------------------------------------------------------------ S1
def s1_policy_comparison(seeds=range(5), policies=None):
    policies = policies or POLICIES
    cfgs = []
    for p in policies:
        c = SimConfig()
        c.scheduler.policy = p
        cfgs.append(c)
    recs = _sweep(cfgs, seeds, label_fn=lambda c: dict(policy=c.scheduler.policy))
    return _agg(recs, "policy")


# ------------------------------------------------------------------------ S2
def s2_budget_sweep(seeds=range(3), duty=(0.001, 0.005, 0.01, 0.05), policies=("fifo", "bacs_gated")):
    cfgs = []
    for d in duty:
        for p in policies:
            c = SimConfig()
            c.lora.duty_cycle = d
            c.scheduler.policy = p
            cfgs.append(c)
    # unconstrained arm, carrying H4
    for p in policies:
        c = SimConfig()
        c.scheduler.policy = p
        c.scheduler.unlimited_budget = True
        c.lora.duty_cycle = 1.0
        cfgs.append(c)
    recs = _sweep(cfgs, seeds, label_fn=lambda c: dict(
        duty=c.lora.duty_cycle if not c.scheduler.unlimited_budget else np.inf,
        policy=c.scheduler.policy))
    return _agg(recs, ["duty", "policy"])


# ------------------------------------------------------------------------ S3
def s3_channel(seeds=range(3), policies=("fifo", "bacs_gated")):
    conds = [("ideal", "independent", 0.0, 0.0),
             ("delay_0.2", "independent", 0.0, 0.2),
             ("loss_10", "independent", 0.10, 0.0),
             ("loss_30", "independent", 0.30, 0.0),
             ("burst_30", "burst", 0.30, 0.0),
             ("worst", "burst", 0.30, 0.2)]
    cfgs = []
    for name, model, loss, dly in conds:
        for p in policies:
            c = SimConfig()
            c.channel.loss_model = model
            c.channel.loss_rate = loss
            c.channel.extra_delay_s = dly
            c.scheduler.policy = p
            c.__dict__["_cond"] = name
            cfgs.append(c)
    recs = _sweep(cfgs, seeds, label_fn=lambda c: dict(
        condition=c.__dict__.get("_cond"), policy=c.scheduler.policy))
    return _agg(recs, ["condition", "policy"])


# ------------------------------------------------------------------------ S4
def s4_gamma(seeds=range(3), gammas=(0.001, 0.003, 0.005, 0.01, 0.03, 0.10, 0.30),
             policy="bacs_gated"):
    """Tests H1: does Eq. (16) predict the empirical optimum?"""
    cfgs = []
    for g in gammas:
        c = SimConfig()
        c.trust.gamma = g
        c.trust.gamma_rule = "fixed"
        c.scheduler.policy = policy
        cfgs.append(c)
    for rule in ("derived", "adaptive"):
        c = SimConfig()
        c.trust.gamma_rule = rule
        c.scheduler.policy = policy
        cfgs.append(c)
    recs = _sweep(cfgs, seeds, label_fn=lambda c: dict(
        gamma_setting=(f"{c.trust.gamma:.3f}" if c.trust.gamma_rule == "fixed"
                       else c.trust.gamma_rule)))
    out = _agg(recs, "gamma_setting")
    base = SimConfig()
    out.attrs["gamma_star"] = gamma_derived(base.world, base.trust)
    return out


# ------------------------------------------------------------------------ S5
def s5_ablation(seeds=range(5)):
    """Utility ablation. Each row removes one factor from Eq. (13)."""
    variants = [
        ("full BACS (gated)",      dict(policy="bacs_gated")),
        ("multiplicative Eq.(13)", dict(policy="bacs")),
        ("trust term only",        dict(policy="greedy_trust")),
        ("info term only",         dict(policy="greedy_info")),
        ("no cost term",           dict(policy="bacs", use_cost_term=False)),
        ("no ageing",              dict(policy="bacs_gated", use_ageing=False)),
        ("FIFO baseline",          dict(policy="fifo")),
        ("send-all (non-compliant)", dict(policy="send_all")),
    ]
    cfgs, names = [], []
    for name, kw in variants:
        c = SimConfig()
        for k, v in kw.items():
            setattr(c.scheduler, k, v)
        c.__dict__["_name"] = name
        cfgs.append(c)
        names.append(name)
    recs = _sweep(cfgs, seeds, label_fn=lambda c: dict(variant=c.__dict__.get("_name")))
    out = _agg(recs, "variant")
    order = {n: i for i, n in enumerate(names)}
    out["_o"] = out["variant"].map(order)
    return out.sort_values("_o").drop(columns="_o").reset_index(drop=True)


# ------------------------------------------------------------------------ S6
def s6_scalability(seeds=range(3), counts=(2, 3, 4, 5), policies=("fifo", "bacs_gated"),
                   session_s=480.0):
    """Tests H3: per-robot airtime falls as 1/N, so the scheduling gap should widen."""
    recs = []
    for n in counts:
        for s in seeds:
            base = _mk(seed=s, n_robots=n)
            base.world.session_s = session_s
            pre = precompute(base)
            for p in policies:
                c = SimConfig()
                c.seed = s
                c.world.n_robots = n
                c.world.session_s = session_s
                c.scheduler.policy = p
                r = run(c, precomputed=pre)
                recs.append(dict(n_robots=n, policy=p, seed=s,
                                 pose_rmse=r.pose_rmse, align_rmse=r.align_rmse,
                                 trust_yield=r.trust_yield, n_delivered=r.n_delivered,
                                 sched_ms=r.sched_overhead_ms))
    return _agg(recs, ["n_robots", "policy"])


def wilcoxon(a, b):
    """Signed-rank test, matching the parent paper's statistical protocol."""
    from scipy.stats import wilcoxon as _w
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 5:
        return dict(W=np.nan, p=np.nan, n=int(m.sum()))
    st = _w(a[m], b[m])
    return dict(W=float(st.statistic), p=float(st.pvalue), n=int(m.sum()))
