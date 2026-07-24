"""
Information gain.

Eq. (11) gives the exact criterion, which needs marginal covariances from the
global graph and is therefore unavailable at the transmitter.  Eq. (12) is the
surrogate the robot can actually compute.  Both are implemented here: the
surrogate for use in scheduling, the exact form for the offline rank-correlation
validation specified in Section 4.4.
"""
import numpy as np

from .config import InfoGainConfig


class CoverageMap:
    """Per-peer bitmap of which cells already have a transmitted constraint."""

    def __init__(self, cfg: InfoGainConfig):
        self.cfg = cfg
        self.cells = set()

    def _key(self, xy):
        c = self.cfg.cell_size
        return (int(np.floor(xy[0] / c)), int(np.floor(xy[1] / c)))

    def novelty(self, xy) -> float:
        """Fraction of the constraint's support not already covered."""
        c = self.cfg.cell_size
        r = int(np.ceil(self.cfg.support_radius / c))
        k0 = self._key(xy)
        total = new = 0
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx * dx + dy * dy > r * r:
                    continue
                total += 1
                if (k0[0] + dx, k0[1] + dy) not in self.cells:
                    new += 1
        return new / max(total, 1)

    def mark(self, xy):
        c = self.cfg.cell_size
        r = int(np.ceil(self.cfg.support_radius / c))
        k0 = self._key(xy)
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    self.cells.add((k0[0] + dx, k0[1] + dy))


# ------------------------------------------------------------------ Eq. (12)
def surrogate_info(novelty: float, degree: int, loop_len: float,
                   cfg: InfoGainConfig, degree_ref: int = 8,
                   loop_ref: float = 60.0) -> float:
    """I_hat = w_v*novelty + w_d*(1 - degree_bar) + w_l*loop_bar."""
    d_bar = min(degree / max(degree_ref, 1), 1.0)
    l_bar = min(loop_len / max(loop_ref, 1e-9), 1.0)
    return float(cfg.w_novelty * novelty
                 + cfg.w_degree * (1.0 - d_bar)
                 + cfg.w_loop * l_bar)


# ------------------------------------------------------------------ Eq. (11)
def exact_info_gain(H: np.ndarray, idx_i, idx_j, omega: np.ndarray) -> float:
    """
    I = 0.5 * log det(I + Omega * Sigma_ij), with Sigma_ij the marginal
    covariance of the relative pose recovered from the graph Hessian.

    Used only in post-hoc analysis, where the converged Hessian is available.
    """
    try:
        Sigma = np.linalg.inv(H + 1e-9 * np.eye(H.shape[0]))
    except np.linalg.LinAlgError:
        return 0.0
    ii = np.array(idx_i)
    jj = np.array(idx_j)
    Sii = Sigma[np.ix_(ii, ii)]
    Sjj = Sigma[np.ix_(jj, jj)]
    Sij = Sigma[np.ix_(ii, jj)]
    Srel = Sii + Sjj - Sij - Sij.T
    M = np.eye(3) + omega @ Srel
    sign, logdet = np.linalg.slogdet(M)
    return float(0.5 * logdet) if sign > 0 else 0.0


def rank_correlation(a, b) -> float:
    """Spearman rho without a scipy dependency at call sites."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    if len(a) < 3:
        return float("nan")
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean()
    rb -= rb.mean()
    den = np.sqrt((ra ** 2).sum() * (rb ** 2).sum())
    return float((ra * rb).sum() / den) if den > 0 else float("nan")
