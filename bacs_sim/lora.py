"""
Physical-layer model. Implements Paper A Section 3.1 (airtime budget) and
Section 3.2 (packet cost), plus the channel emulator used to produce the
measured delay the server sees.
"""
import math
import numpy as np

from .config import LoRaConfig, ChannelConfig


# ---------------------------------------------------------------- Eqs. (2)-(4)
def symbol_time(cfg: LoRaConfig) -> float:
    """T_sym = 2^SF / BW.  Eq. (2)."""
    return (2 ** cfg.sf) / cfg.bw


def payload_symbols(payload_bytes: int, cfg: LoRaConfig) -> int:
    """n_pay.  Eq. (3).  Standard LoRa modulation model."""
    de = 1 if cfg.low_data_rate_opt else 0
    ih = 1 if cfg.implicit_header else 0
    crc = 1 if cfg.crc else 0
    num = 8 * payload_bytes - 4 * cfg.sf + 28 + 16 * crc - 20 * ih
    den = 4 * (cfg.sf - 2 * de)
    return 8 + max(math.ceil(num / den) * (cfg.cr + 4), 0)


def time_on_air(payload_bytes: int, cfg: LoRaConfig) -> float:
    """T_air(PL).  Eq. (4).  Step function of payload size."""
    t_sym = symbol_time(cfg)
    t_pre = (cfg.n_preamble + 4.25) * t_sym
    return t_pre + payload_symbols(payload_bytes, cfg) * t_sym


def airtime_budget(window_s: float, cfg: LoRaConfig, n_robots: int = 1) -> float:
    """
    B(W) = delta * W.  Eq. (1).

    With n_robots sharing one channel and no coordination protocol, the usable
    per-robot share approaches delta*W/N.  This division is the mechanism
    behind Hypothesis H3.
    """
    return cfg.duty_cycle * window_s / max(n_robots, 1)


# ------------------------------------------------------------------- channel
class Channel:
    """
    Emulates loss and delay on the shared link.

    Two loss models are provided.  The independent model matches the assumption
    behind Eq. (6).  The burst model (Gilbert-Elliott) deliberately violates it,
    so that Scenario 3 can measure how optimistic the delay predictor becomes
    when losses are correlated.
    """

    def __init__(self, cfg: ChannelConfig, lora: LoRaConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.lora = lora
        self.rng = rng
        self._bad = False
        # Gilbert-Elliott transition probabilities from the requested stationary
        # occupancy and mean burst length.
        if cfg.ge_mean_burst > 1.0:
            self.p_bad_good = 1.0 / cfg.ge_mean_burst          # bad -> good
        else:
            self.p_bad_good = 1.0
        pb = min(max(cfg.ge_p_bad, 1e-6), 1 - 1e-6)
        self.p_good_bad = self.p_bad_good * pb / (1 - pb)      # good -> bad

    def _step_state(self):
        if self._bad:
            if self.rng.random() < self.p_bad_good:
                self._bad = False
        else:
            if self.rng.random() < self.p_good_bad:
                self._bad = True

    def _drop_prob(self) -> float:
        if self.cfg.loss_model == "burst":
            self._step_state()
            return self.cfg.ge_loss_bad if self._bad else self.cfg.ge_loss_good
        return self.cfg.loss_rate

    def transmit(self, payload_bytes: int, t_ready: float):
        """
        Attempt delivery of one packet offered to the radio at t_ready.

        Returns (delivered, t_recv, airtime_consumed, n_attempts).  Airtime is
        charged for every attempt including failures, because a lost packet
        still occupied the channel and still counts against the duty cycle.
        """
        t_air = time_on_air(payload_bytes, self.lora)
        t = t_ready
        used = 0.0
        for attempt in range(self.cfg.max_retries + 1):
            t += t_air
            used += t_air
            if self.rng.random() >= self._drop_prob():
                return True, t + self.cfg.extra_delay_s, used, attempt + 1
            t += self.lora.ack_timeout_s
        return False, t, used, self.cfg.max_retries + 1
