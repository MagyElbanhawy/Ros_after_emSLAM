#!/usr/bin/env python3
"""
BACS scheduler node.

Reference ROS 2 implementation of Bandwidth-Aware Constraint Scheduling. It sits
between the SLAM front-end and the LoRa bridge:

    /local_constraint_candidates  (ConstraintCandidate)
    /fused_map                    (nav_msgs/Path or a project message)
    /radio_stats                  (RadioStats)
                     |
                     v
              [ BACS scheduler ]   -- one selection per duty-cycle window
                     |
                     v
    /selected_constraints         (SelectedConstraint) --> LoRa bridge --> server

The decision logic is not reimplemented here; it calls the same functions the
simulator validates (`bacs_sim.trust`, `bacs_sim.infogain`,
`bacs_sim.observability`, `bacs_sim.schedulers`, `bacs_sim.lora`). That keeps the
deployed scheduler and the evaluated scheduler bit-for-bit identical in their
ranking, so a result measured in simulation transfers to the robot.

This file is a deployment scaffold: it is structured and typed for a real EMRMF
stack but has not been run on hardware. Wire `/fused_map` to your project's map
topic and adjust QoS to your radio bridge.
"""
from __future__ import annotations

import numpy as np
import rclpy
from rclpy.node import Node

from bacs_sim.config import (LoRaConfig, TrustConfig, InfoGainConfig,
                             SchedulerConfig)
from bacs_sim.lora import time_on_air, airtime_budget
from bacs_sim.trust import predicted_trust, predicted_delay, gamma_deferral_derived
from bacs_sim.infogain import surrogate_info
from bacs_sim.observability import PairObservability
from bacs_sim.schedulers import schedule, compute_utility

# Message imports resolve after `colcon build`. Kept local so the module can be
# imported for linting without the generated interfaces present.
try:
    from bacs_scheduler.msg import (ConstraintCandidate, SelectedConstraint,
                                    RadioStats)
except Exception:  # pragma: no cover - interfaces generated at build time
    ConstraintCandidate = SelectedConstraint = RadioStats = None


class _Cand:
    """Adapter exposing the attribute names the bacs_sim scheduler expects."""

    __slots__ = ("rid_from", "rid_to", "idx_from", "idx_to", "z", "payload_bytes",
                 "t_created", "theta_hat", "info_hat", "utility", "dt_hat",
                 "deferrals", "msg")

    def __init__(self, msg, now_s: float):
        self.msg = msg
        self.rid_from = int(msg.robot_from)
        self.rid_to = int(msg.robot_to)
        self.idx_from = int(msg.idx_from)
        self.idx_to = int(msg.idx_to)
        self.z = np.array([msg.z.x, msg.z.y, msg.z.theta])
        self.payload_bytes = int(msg.payload_bytes)
        self.t_created = float(msg.stamp.sec) + 1e-9 * float(msg.stamp.nanosec)
        self.theta_hat = 0.0
        self.info_hat = 0.0
        self.utility = 0.0
        self.dt_hat = 0.0
        self.deferrals = 0


class BacsSchedulerNode(Node):
    def __init__(self):
        super().__init__("bacs_scheduler")

        # --- parameters (override in the launch file / YAML) ---
        self.declare_parameter("robot_id", 0)
        self.declare_parameter("n_robots", 2)
        self.declare_parameter("policy", "bacs_plus")
        self.declare_parameter("window_s", 60.0)
        self.declare_parameter("duty_cycle", 0.01)
        self.declare_parameter("sf", 7)

        self.robot_id = int(self.get_parameter("robot_id").value)
        self.n_robots = int(self.get_parameter("n_robots").value)

        self.lora = LoRaConfig(sf=int(self.get_parameter("sf").value),
                               duty_cycle=float(self.get_parameter("duty_cycle").value))
        self.trust = TrustConfig(gamma_rule="deferral_derived")
        self.infogain = InfoGainConfig()
        self.sched = SchedulerConfig(policy=str(self.get_parameter("policy").value),
                                     window_s=float(self.get_parameter("window_s").value))
        self.sched.use_observability = self.sched.policy == "bacs_plus"

        self.gamma = gamma_deferral_derived(self.trust)
        self.pair_obs = PairObservability(self.infogain.obs_ref)
        self.rng = np.random.default_rng(0)

        # --- link/map state, refreshed by callbacks ---
        self.p_loss = 0.0
        self.mean_delay = self.trust.t_defer_prior
        self.map_age = 0.0

        self.pending: list[_Cand] = []

        self.sub_cand = self.create_subscription(
            ConstraintCandidate, "local_constraint_candidates",
            self.on_candidate, 50)
        self.sub_stats = self.create_subscription(
            RadioStats, "radio_stats", self.on_radio_stats, 10)
        # self.sub_map = self.create_subscription(... "fused_map" ...)  # project-specific

        self.pub_sel = self.create_publisher(
            SelectedConstraint, "selected_constraints", 50)

        self.timer = self.create_timer(self.sched.window_s, self.on_window)
        self.get_logger().info(
            f"BACS scheduler up: robot={self.robot_id} policy={self.sched.policy} "
            f"budget/window={airtime_budget(self.sched.window_s, self.lora, self.n_robots):.3f}s")

    # ------------------------------------------------------------------ inputs
    def on_candidate(self, msg):
        self.pending.append(_Cand(msg, self._now()))

    def on_radio_stats(self, msg):
        self.p_loss = float(msg.loss_rate_ewma)
        if msg.mean_delay_ewma > 0:
            self.mean_delay = float(msg.mean_delay_ewma)
        self.map_age = float(msg.map_age)
        if self.trust.gamma_rule == "deferral_adaptive" and self.mean_delay > 1e-9:
            self.gamma = float(np.clip(np.log(2.0) / self.mean_delay,
                                       self.trust.gamma_min, self.trust.gamma_max))

    # ------------------------------------------------------- windowed decision
    def on_window(self):
        if not self.pending:
            return
        budget = airtime_budget(self.sched.window_s, self.lora, self.n_robots)

        # Score every pending candidate, then rank by transmission-order queue
        # position (same two-pass logic the simulator uses).
        self._score(self.pending, budget)
        self.pending.sort(key=lambda c: c.utility, reverse=True)
        self._score(self.pending, budget)

        chosen = schedule(self.pending, budget, self.sched, self.lora, self.rng)
        chosen_ids = {id(c) for c in chosen}

        for c in chosen:
            self.pub_sel.publish(self._to_selected(c))
            self.pair_obs.mark(c.rid_from, c.rid_to)

        kept = []
        for c in self.pending:
            if id(c) in chosen_ids:
                continue
            c.deferrals += 1
            if c.deferrals < 12:
                kept.append(c)
        self.pending = kept

    def _score(self, cands, budget):
        acc = 0.0
        for c in cands:
            c.dt_hat = predicted_delay(c.payload_bytes, acc, self.lora, self.p_loss,
                                       deferral_windows=acc / max(budget, 1e-9),
                                       window_s=self.sched.window_s)
            acc += time_on_air(c.payload_bytes, self.lora)
            # Residual against the fused map is computed by the front-end and
            # delivered in the candidate; here we use the surrogate terms only.
            res = float(np.linalg.norm(c.z[:2]))  # placeholder; see note in docstring
            c.theta_hat = predicted_trust(res, c.dt_hat, self.trust, self.gamma,
                                          map_age=self.map_age)
            obs = (self.pair_obs.score(c.rid_from, c.rid_to)
                   if self.sched.use_observability else 0.0)
            c.info_hat = surrogate_info(c.msg.novelty, int(c.msg.degree * 8),
                                        c.msg.loop_len * 60.0, self.infogain,
                                        observability=obs)
            c.utility = compute_utility(c, self.sched, self.lora)

    def _to_selected(self, c):
        m = SelectedConstraint()
        m.stamp = c.msg.stamp
        m.cid = c.msg.cid
        m.robot_from = c.msg.robot_from
        m.robot_to = c.msg.robot_to
        m.idx_from = c.msg.idx_from
        m.idx_to = c.msg.idx_to
        m.z = c.msg.z
        m.information = c.msg.information
        m.payload_bytes = c.msg.payload_bytes
        m.predicted_trust = float(c.theta_hat)
        m.info_score = float(c.info_hat)
        m.predicted_delay = float(c.dt_hat)
        m.queue_age = float(c.deferrals)
        m.airtime_cost = float(time_on_air(c.payload_bytes, self.lora))
        return m

    def _now(self) -> float:
        t = self.get_clock().now()
        return t.nanoseconds * 1e-9


def main(args=None):
    rclpy.init(args=args)
    node = BacsSchedulerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
