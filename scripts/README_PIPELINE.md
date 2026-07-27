#!/usr/bin/env python3
"""
README: BACS+ Experimental Validation Pipeline

This package provides a complete pipeline for real-world validation of the BACS+ scheduler.

## Quick Start

### 1. Setup Experiment Directory Structure
```bash
python3 scripts/directory_setup.py \
  --base-dir ./experiment_results \
  --policies bacs_plus greedy random \
  --runs 10
```

### 2. Run Physical Experiments

#### Single Run
```bash
bash ros2_ws/src/bacs_scheduler/scripts/run_physical_session.sh bacs_plus session_001 robot_0
```

#### Batch Runs (All Policies)
```bash
python3 scripts/batch_runner.py \
  --policies bacs_plus greedy random \
  --runs 10 \
  --robot-name robot_0
```

### 3. Analyze Results
```bash
python3 scripts/analysis_pipeline.py \
  --experiment-dir ./experiment_results \
  --output-dir ./analysis_results \
  --policy bacs_plus
```

## Expected Output Files

### From BACS Scheduler Node
**File**: `bacs_logs/bacs_scheduler_log_<session>_<policy>_YYYYMMDD_HHMMSS.csv`

```csv
seq_id,t_gen_ns,t_selected_ns,t_tx_ns,t_rx_ns,selected_policy,constraint_count
0,1627000000000000000,1627000000000100000,1627000000000600000,1627000000050600000,bacs_plus,1
1,1627000001000000000,1627000001000150000,1627000001000650000,1627000001051650000,bacs_plus,2
```

**Columns**:
- `seq_id`: Constraint sequence number
- `t_gen_ns`: Generation timestamp (nanoseconds)
- `t_selected_ns`: Selection timestamp (nanoseconds)
- `t_tx_ns`: Transmission timestamp (nanoseconds)
- `t_rx_ns`: Reception timestamp (nanoseconds)
- `selected_policy`: Policy used for selection
- `constraint_count`: Total constraints processed

**Calculations**:
- **T_defer** = (t_selected_ns - t_gen_ns) / 1000 [microseconds]
- **T_channel** = (t_rx_ns - t_tx_ns) / 1000 [microseconds]

### From Vicon Logger Node
**File**: `vicon_logs/vicon_ground_truth_<session>_<robot>_YYYYMMDD_HHMMSS.csv`

```csv
timestamp_ns,x,y,z,roll_rad,pitch_rad,yaw_rad,vx,vy,vz
1627000000000000000,0.000000,0.000000,0.100000,0.000000,0.000000,0.000000,0.000000,0.000000,0.000000
1627000000050000000,0.001250,0.000000,0.100000,0.000000,0.000000,0.001000,0.025000,0.000000,0.000000
```

**Columns**:
- `timestamp_ns`: Measurement timestamp (nanoseconds)
- `x, y, z`: Position (meters)
- `roll_rad, pitch_rad, yaw_rad`: Orientation (radians)
- `vx, vy, vz`: Velocity (m/s)

**Metrics**:
- **Map-Alignment RMSE**: Trajectory alignment quality
- **Pose RMSE**: Position and orientation error vs ground truth

### ROS 2 Bag Recordings
**File**: `rosbags/<session>_<policy>_YYYYMMDD_HHMMSS.db3`

Complete recording of all ROS 2 messages for debugging and post-processing.

## Analysis Pipeline

The analysis pipeline performs:

1. **Timing Analysis**
   - Parse scheduler logs
   - Calculate T_defer and T_channel per constraint
   - Compute statistics: mean, std, median, p95, p99
   - Generate timing histograms

2. **Pose Analysis**
   - Parse Vicon ground truth logs
   - Calculate Map-Alignment RMSE (trajectory alignment)
   - Calculate Pose RMSE (position + orientation error)
   - Generate trajectory visualizations

3. **Statistical Testing**
   - **Wilcoxon Signed-Rank Test**: Non-parametric comparison of policies
   - **Mann-Whitney U Test**: For unequal sample sizes
   - **Cliff's Delta**: Effect size (negligible/small/medium/large)

4. **Results Export**
   - JSON: Full results with metadata
   - CSV: Tabular results for spreadsheet analysis
   - Figures: Publication-ready plots (timing, trajectory, statistics)

## Requirements

```
rclpy>=3.1
numpy>=1.21
scipy>=1.7
matplotlib>=3.4
```

Install with:
```bash
pip install -r requirements.txt
```

## Experimental Design

### HP1: BACS+ Reduces Scheduling Latency

**Hypothesis**: BACS+ selection (T_defer) is significantly lower than baseline policies.

**Validation**:
1. Run 10+ trials per policy
2. Extract T_defer values from logs
3. Perform Wilcoxon test: H₀: T_defer(BACS+) = T_defer(baseline)
4. Report p-value and Cliff's δ

### HP2: Channel Overhead is Predictable

**Hypothesis**: T_channel variance is low (deterministic communication).

**Validation**:
1. Extract T_channel from all constraints
2. Calculate coefficient of variation (std/mean)
3. Compare across policies (should be similar)

### HP3: Trajectory Quality is Maintained

**Hypothesis**: Map-Alignment RMSE is consistent across policies.

**Validation**:
1. Calculate Map-Alignment RMSE for each run
2. Verify RMSE < threshold (e.g., 0.05 m)
3. Perform Kruskal-Wallis test (no significant differences)

## Troubleshooting

### Missing CSV files
- Verify nodes launched successfully: check `ros2 node list`
- Check log directory permissions
- Verify ROS 2 topics are being published

### Empty CSV files
- Scheduler may not be receiving constraints
- Vicon system may not be connected
- Check ROS 2 bag for message content

### Analysis errors
- Ensure CSV column names match expected format
- Verify timestamp values are in nanoseconds (large positive integers)
- Check for NaN values in position/orientation data

## References

Appendix A.4: Latency Measurement Protocol
- Details on timestamp collection
- Validation procedures for timing measurements
- Synchronization requirements

Table A2: Pose RMSE Results
- Required format for results presentation
- Statistical significance thresholds
- Publication guidelines
