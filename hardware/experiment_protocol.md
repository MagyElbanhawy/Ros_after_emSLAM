# BACS hardware experiment protocol

A procedure for reproducing the simulator's headline comparison (FIFO vs BACS
vs BACS+) on physical robots over a real LoRa link. This is the validation the
simulator's findings point to; it has not yet been run.

## 1. Platform

- 2–5 differential-drive robots, each with a 2D LiDAR or RGB-D front-end running
  the EMRMF local mapping stack under ROS 2.
- One RYLR998 (SX1262) LoRa module per robot, configured per
  `hardware/lora_parameters.yaml`, plus one module at the fusion server.
- A workstation acting as the EMRMF fusion server (g2o / GTSAM back-end).

## 2. Environment

- Indoor space ≥ 150 m² with overlapping robot territories (~15% overlap on
  interior boundaries), matching the simulator's boustrophedon coverage.
- Fixed ground-truth reference: motion capture, or surveyed AprilTags with a
  total-station-registered map. Record ground-truth poses at ≥ 10 Hz.

## 3. Fixed factors (hold constant across arms)

- Trajectory schedule and start poses (replay the same waypoint plan each run).
- Radio configuration (SF7/BW125, 1% duty cycle, 14 dBm).
- Session length: 12 min. Duty-cycle window W = 60 s.
- Decay coefficient rule: `deferral_derived` (γ = ln2 / T_defer).

## 4. Arms

| Arm | Scheduler `policy` | Notes |
|---|---|---|
| A | `fifo` | duty-cycle-compliant baseline |
| B | `bacs_gated` | trust-gated, info-density ranking |
| C | `bacs_plus` | + observability term |
| (ref) | `fifo`, drift γ | EMRMF-original, γ from Eq. (16) |

Randomise arm order across sessions to balance drift in ambient RF and battery
state. Run ≥ 20 sessions per arm (seeded trajectory noise where applicable) so
the Wilcoxon signed-rank test has power comparable to the simulation.

## 5. Measurements (per session)

- Per-step position RMSE vs ground truth (primary).
- Inter-robot map alignment error on ground-truth co-location pairs.
- Airtime utilisation and duty-cycle compliance (log every transmission's ToA).
- Delivered constraint count, mean end-to-end delay, and deferral distribution.
- Trust yield (mean server-side θ over delivered constraints).

Log `SelectedConstraint` messages (predicted trust, info score, predicted delay,
queue age, airtime cost) for every packet so simulation and hardware decisions
can be compared candidate-by-candidate.

## 6. Analysis

1. Verify duty-cycle compliance: measured per-device occupancy ≤ 1% in every
   window. Discard any session that violates it.
2. Primary: paired Wilcoxon signed-rank on per-session RMSE, B vs A and C vs A;
   report the median improvement, 95% CI, and Cliff's δ (see
   `bacs_sim.experiments.summary_stats` / `cliffs_delta`).
3. Scalability: repeat for N = 2..5 robots and check whether the C-vs-A
   advantage persists where B-vs-A reverses (the H3 / observability question).
4. Surrogate check: from the server's converged graph, compute exact
   information gain for delivered constraints and correlate with the logged
   `info_score` (the hardware analogue of Scenario S7).

## 7. Safety / logistics

- Charge to a fixed floor before each session; log battery voltage (affects TX).
- Keep a co-channel RF monitor running to attribute losses to interference vs
  scheduling.
