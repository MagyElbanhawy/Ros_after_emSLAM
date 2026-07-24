# bacs_scheduler (ROS 2)

Reference ROS 2 node that runs Bandwidth-Aware Constraint Scheduling on a real
EMRMF-style pipeline. It wraps the **same** decision functions the simulator
validates (`bacs_sim.trust`, `bacs_sim.infogain`, `bacs_sim.observability`,
`bacs_sim.schedulers`, `bacs_sim.lora`), so the deployed ranking is identical to
the evaluated one.

> **Status:** deployment scaffold. The node is structured and typed for a real
> stack but has **not** been run on hardware. In particular, wire `/fused_map`
> to your project's fused-map topic and replace the placeholder provisional
> residual in `_score()` with the residual your front-end computes against that
> map (Eq. 8 requires the fused map, not raw odometry — see paper §4.4).

## Topics

| Direction | Topic | Type |
|---|---|---|
| in  | `local_constraint_candidates` | `bacs_scheduler/ConstraintCandidate` |
| in  | `radio_stats` | `bacs_scheduler/RadioStats` |
| in  | `fused_map` *(project-specific, TODO)* | e.g. `nav_msgs/Path` |
| out | `selected_constraints` | `bacs_scheduler/SelectedConstraint` |

`SelectedConstraint` carries the decision variables (predicted trust, info
score, predicted delay, queue age, airtime cost) so the fusion server and any
offline ablation can see why each packet was chosen.

## Build & run

```bash
cd ros2_ws
# bacs_sim must be importable by the node's Python interpreter:
pip install -e ..          # installs the bacs-sim package from the repo root
colcon build --packages-select bacs_scheduler
source install/setup.bash
ros2 launch bacs_scheduler bacs_scheduler.launch.py
```

Parameters (see `config/bacs.yaml`): `robot_id`, `n_robots`, `policy`
(`fifo`/`bacs`/`bacs_gated`/`bacs_plus`), `window_s`, `duty_cycle`, `sf`.

## Data flow

```
/slam/constraint_candidates ->  BACS scheduler  -> /lora/tx_constraints -> LoRa bridge -> EMRMF fusion server
/lora/stats  ------------------->               (per duty-cycle window)
/fused_map   ------------------->
```
