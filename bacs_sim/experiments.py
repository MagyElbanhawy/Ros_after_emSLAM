"""
Scenario runners.  Each returns a pandas DataFrame ready for the manuscript.

S1  scheduling policy comparison
S2  airtime budget sweep
S3  channel robustness
S4  decay coefficient study (tests H1)
S5  utility ablation
S6  scalability (tests H3)
S7  information-surrogate validation (Spearman rho vs exact MI)
S8  observability ablation (BACS vs BACS+ across team size)
S9  decay-coefficient rule comparison (deferral vs drift derivations)
"""
import numpy as np
import pandas as pd
from dataclasses import replace

from .config import SimConfig
from .simulator import run, precompute, _odometry_information
from .trust import gamma_derived, gamma_deferral_derived
from .infogain import exact_info_from_cov, rank_correlation
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


# ------------------------------------------------------------------------ S7
def s7_surrogate_validation(seeds=range(3), counts=(2, 3, 4, 5),
                            policy="bacs_gated", session_s=480.0):
    """Validate the Eq. (12) surrogate against the exact information of Eq. (11).

    For each run we take the delivered constraints, recover the marginal
    covariance of every constrained relative pose from the converged graph
    Hessian, evaluate exact mutual information, and correlate it (Spearman rho)
    with the surrogate score the scheduler used. Reported per team size, because
    Section 6.5 conjectures that surrogate fidelity degrades as N grows and that
    this is why the scheduling advantage reverses.
    """
    recs = []
    for n in counts:
        for s in seeds:
            c = _mk(seed=s, n_robots=n)
            c.world.session_s = session_s
            c.scheduler.policy = policy
            pre = precompute(c)
            r = run(c, precomputed=pre, collect_graph=True)
            graph = r.extras["graph"]
            H = r.extras["hessian"]
            omega = r.extras["omega"]
            delivered = r.extras["delivered"]
            rho, npairs = _surrogate_rho(graph, H, omega, delivered)
            recs.append(dict(n_robots=n, seed=s, rho=rho, n_pairs=npairs,
                             n_delivered=r.n_delivered, pose_rmse=r.pose_rmse))
    return _agg(recs, "n_robots")


def _surrogate_rho(graph, H, omega, delivered):
    """Spearman rho between surrogate info and exact MI over delivered edges."""
    if H is None or not delivered:
        return float("nan"), 0
    Hd = H.toarray() if hasattr(H, "toarray") else np.asarray(H)
    try:
        Sigma = np.linalg.inv(Hd + 1e-9 * np.eye(Hd.shape[0]))
    except np.linalg.LinAlgError:
        return float("nan"), 0
    surro, exact = [], []
    for c in delivered:
        i = graph.idx((c.rid_from, c.idx_from))
        j = graph.idx((c.rid_to, c.idx_to))
        if i is None or j is None:
            continue
        surro.append(c.info_hat)
        exact.append(exact_info_from_cov(Sigma, i, j, omega))
    return rank_correlation(surro, exact), len(surro)


# ------------------------------------------------------------------------ S8
def s8_observability(seeds=range(5), counts=(2, 3, 4, 5), session_s=480.0):
    """Observability ablation: does the BACS+ term recover the large-team regime?

    Compares FIFO, plain gated BACS, and BACS+ across team size. The plain
    scheduler's advantage over FIFO is known to reverse beyond three robots
    (H3); this measures whether adding the observability term keeps pose RMSE
    below FIFO where the plain surrogate does not.
    """
    recs = []
    for n in counts:
        for s in seeds:
            base = _mk(seed=s, n_robots=n)
            base.world.session_s = session_s
            pre = precompute(base)
            for p in ("fifo", "bacs_gated", "bacs_plus"):
                c = SimConfig()
                c.seed = s
                c.world.n_robots = n
                c.world.session_s = session_s
                c.scheduler.policy = p
                # Use the corrected (deferral-derived) decay coefficient on every
                # arm so the observability comparison is not confounded by an
                # uncalibrated gamma.
                c.trust.gamma_rule = "deferral_derived"
                r = run(c, precomputed=pre)
                recs.append(dict(n_robots=n, policy=p, seed=s,
                                 pose_rmse=r.pose_rmse, align_rmse=r.align_rmse,
                                 trust_yield=r.trust_yield,
                                 n_delivered=r.n_delivered))
    return _agg(recs, ["n_robots", "policy"])


# ------------------------------------------------------------------------ S9
def s9_deferral_gamma(seeds=range(5), policy="bacs_gated"):
    """Compare decay-coefficient rules, including the corrected deferral rules.

    Rows: fixed at the empirical optimum, the original drift derivation (Eq. 16)
    and its adaptive variant (both falsified in S4), and the two deferral-based
    rules that anchor gamma to the airtime-queueing timescale instead.
    """
    variants = [
        ("fixed 0.003",        dict(gamma_rule="fixed", gamma=0.003)),
        ("drift derived",      dict(gamma_rule="derived")),
        ("drift adaptive",     dict(gamma_rule="adaptive")),
        ("deferral derived",   dict(gamma_rule="deferral_derived")),
        ("deferral adaptive",  dict(gamma_rule="deferral_adaptive")),
    ]
    cfgs, names = [], []
    for name, kw in variants:
        c = SimConfig()
        c.scheduler.policy = policy
        for k, v in kw.items():
            setattr(c.trust, k, v)
        c.__dict__["_name"] = name
        cfgs.append(c)
        names.append(name)
    recs = _sweep(cfgs, seeds, label_fn=lambda c: dict(rule=c.__dict__.get("_name")))
    out = _agg(recs, "rule")
    order = {n: i for i, n in enumerate(names)}
    out["_o"] = out["rule"].map(order)
    out = out.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    base = SimConfig()
    out.attrs["gamma_drift"] = gamma_derived(base.world, base.trust)
    out.attrs["gamma_deferral"] = gamma_deferral_derived(base.trust)
    return out


# --------------------------------------------------------------- EMRMF baseline
def emrmf_baseline() -> SimConfig:
    """The parent framework as-is: FIFO transmission, trust-weighted fusion, and
    the original drift-derived decay coefficient (Eq. 16). The reference point
    the BACS progression is measured against."""
    c = SimConfig()
    c.scheduler.policy = "fifo"
    c.trust.gamma_rule = "derived"
    return c


def progression(seeds=range(5)):
    """Research progression: EMRMF-original -> compliant FIFO -> BACS -> BACS+.

    Each stage changes exactly one thing so the contribution of each step is
    legible: the recalibrated (deferral) gamma, then the gated scheduler, then
    the observability term.
    """
    stages = []

    s0 = emrmf_baseline()
    s0.__dict__["_name"] = "EMRMF-original (FIFO, drift gamma)"
    stages.append(s0)

    s1 = SimConfig()
    s1.scheduler.policy = "fifo"
    s1.trust.gamma_rule = "deferral_derived"
    s1.__dict__["_name"] = "compliant FIFO (deferral gamma)"
    stages.append(s1)

    s2 = SimConfig()
    s2.scheduler.policy = "bacs_gated"
    s2.trust.gamma_rule = "deferral_derived"
    s2.__dict__["_name"] = "BACS (gated)"
    stages.append(s2)

    s3 = SimConfig()
    s3.scheduler.policy = "bacs_plus"
    s3.trust.gamma_rule = "deferral_derived"
    s3.__dict__["_name"] = "BACS+ (observability)"
    stages.append(s3)

    recs = _sweep(stages, seeds, label_fn=lambda c: dict(stage=c.__dict__.get("_name")))
    out = _agg(recs, "stage")
    order = {c.__dict__["_name"]: i for i, c in enumerate(stages)}
    out["_o"] = out["stage"].map(order)
    return out.sort_values("_o").drop(columns="_o").reset_index(drop=True)


def summary_stats(values) -> dict:
    """Mean, std, median and a normal-approximation 95% CI for one metric.

    Reported alongside the Wilcoxon test for the principal comparisons so the
    headline percentages carry dispersion and interval estimates, not point
    values alone.
    """
    a = np.asarray([v for v in values if np.isfinite(v)], float)
    n = len(a)
    if n == 0:
        return dict(n=0, mean=np.nan, std=np.nan, median=np.nan,
                    ci_lo=np.nan, ci_hi=np.nan)
    mean = float(a.mean())
    std = float(a.std(ddof=1)) if n > 1 else 0.0
    half = 1.96 * std / np.sqrt(n) if n > 1 else 0.0
    return dict(n=n, mean=mean, std=std, median=float(np.median(a)),
                ci_lo=mean - half, ci_hi=mean + half)


def cliffs_delta(a, b) -> float:
    """Cliff's delta effect size for two independent samples, in [-1, 1].

    A nonparametric complement to the Wilcoxon p-value: the probability that a
    draw from `a` exceeds a draw from `b`, minus the reverse.
    """
    a = np.asarray([v for v in a if np.isfinite(v)], float)
    b = np.asarray([v for v in b if np.isfinite(v)], float)
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    gt = (a[:, None] > b[None, :]).sum()
    lt = (a[:, None] < b[None, :]).sum()
    return float((gt - lt) / (len(a) * len(b)))
