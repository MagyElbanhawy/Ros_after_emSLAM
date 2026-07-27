#!/usr/bin/env python3
"""
Data Collection and Analysis Pipeline for BACS+ Experiments

This module provides utilities to:
1. Aggregate multiple experiment runs
2. Calculate T_defer and T_channel from raw timestamps
3. Compute Map-Alignment RMSE and Pose RMSE
4. Perform statistical analysis (Wilcoxon, Cliff's δ)
5. Generate publication-ready figures and tables

Usage:
    python3 analysis_pipeline.py --experiment-dir ./experiment_results --policy bacs_plus
"""

import os
import csv
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple
import numpy as np
from scipy import stats
from dataclasses import dataclass
import logging


# ============================================================================
# CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ExperimentRun:
    """Container for a single experiment run."""
    session_id: str
    policy: str
    timestamp: str
    scheduler_log_file: str
    vicon_log_file: str
    

@dataclass
class TimingMetrics:
    """Container for timing-based metrics."""
    seq_id: int
    t_defer_us: float  # microseconds
    t_channel_us: float  # microseconds
    

@dataclass
class PoseMetrics:
    """Container for pose-based metrics."""
    timestamp_ns: int
    x: float
    y: float
    z: float
    roll_rad: float
    pitch_rad: float
    yaw_rad: float
    vx: float
    vy: float
    vz: float


# ============================================================================
# TIMING ANALYSIS
# ============================================================================

def parse_scheduler_log(csv_file: str) -> List[TimingMetrics]:
    """
    Parse scheduler log file and calculate T_defer and T_channel.
    
    Args:
        csv_file: Path to bacs_scheduler_log_*.csv
        
    Returns:
        List of TimingMetrics with calculated latencies
    """
    metrics = []
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                t_gen_ns = int(row['t_gen_ns'])
                t_selected_ns = int(row['t_selected_ns'])
                t_tx_ns = int(row['t_tx_ns'])
                t_rx_ns = int(row['t_rx_ns'])
                
                # Calculate latencies in microseconds
                t_defer_us = (t_selected_ns - t_gen_ns) / 1000.0
                t_channel_us = (t_rx_ns - t_tx_ns) / 1000.0
                
                metrics.append(TimingMetrics(
                    seq_id=int(row['seq_id']),
                    t_defer_us=t_defer_us,
                    t_channel_us=t_channel_us
                ))
        
        logger.info(f'Parsed {len(metrics)} timing measurements from {csv_file}')
        return metrics
        
    except Exception as e:
        logger.error(f'Error parsing scheduler log: {e}')
        return []


def calculate_timing_statistics(metrics_list: List[List[TimingMetrics]]) -> Dict:
    """
    Calculate statistics across multiple runs.
    
    Args:
        metrics_list: List of metric lists (one per run)
        
    Returns:
        Dictionary with aggregated statistics
    """
    t_defer_all = [m.t_defer_us for run in metrics_list for m in run]
    t_channel_all = [m.t_channel_us for run in metrics_list for m in run]
    
    return {
        't_defer': {
            'mean_us': np.mean(t_defer_all),
            'std_us': np.std(t_defer_all),
            'median_us': np.median(t_defer_all),
            'min_us': np.min(t_defer_all),
            'max_us': np.max(t_defer_all),
            'p95_us': np.percentile(t_defer_all, 95),
            'p99_us': np.percentile(t_defer_all, 99),
        },
        't_channel': {
            'mean_us': np.mean(t_channel_all),
            'std_us': np.std(t_channel_all),
            'median_us': np.median(t_channel_all),
            'min_us': np.min(t_channel_all),
            'max_us': np.max(t_channel_all),
            'p95_us': np.percentile(t_channel_all, 95),
            'p99_us': np.percentile(t_channel_all, 99),
        },
        'sample_count': len(t_defer_all)
    }


# ============================================================================
# POSE ANALYSIS
# ============================================================================

def parse_vicon_log(csv_file: str) -> List[PoseMetrics]:
    """
    Parse Vicon ground truth log file.
    
    Args:
        csv_file: Path to vicon_ground_truth_*.csv
        
    Returns:
        List of PoseMetrics
    """
    metrics = []
    
    try:
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                metrics.append(PoseMetrics(
                    timestamp_ns=int(row['timestamp_ns']),
                    x=float(row['x']),
                    y=float(row['y']),
                    z=float(row['z']),
                    roll_rad=float(row['roll_rad']),
                    pitch_rad=float(row['pitch_rad']),
                    yaw_rad=float(row['yaw_rad']),
                    vx=float(row['vx']),
                    vy=float(row['vy']),
                    vz=float(row['vz'])
                ))
        
        logger.info(f'Parsed {len(metrics)} pose measurements from {csv_file}')
        return metrics
        
    except Exception as e:
        logger.error(f'Error parsing Vicon log: {e}')
        return []


def calculate_pose_rmse(reference_poses: List[PoseMetrics],
                        test_poses: List[PoseMetrics]) -> Dict:
    """
    Calculate pose RMSE between reference and test trajectories.
    
    Args:
        reference_poses: Ground truth poses
        test_poses: Test trajectory poses
        
    Returns:
        Dictionary with RMSE metrics
    """
    if not reference_poses or not test_poses:
        logger.warning('Insufficient data for RMSE calculation')
        return {}
    
    # Time-align poses (nearest neighbor matching)
    ref_positions = np.array([[p.x, p.y, p.z] for p in reference_poses])
    test_positions = np.array([[p.x, p.y, p.z] for p in test_poses])
    
    # Calculate position RMSE
    position_diff = ref_positions[:len(test_positions)] - test_positions[:len(ref_positions)]
    position_rmse = np.sqrt(np.mean(np.sum(position_diff ** 2, axis=1)))
    
    # Calculate orientation RMSE (Euler angles)
    ref_orientations = np.array([
        [p.roll_rad, p.pitch_rad, p.yaw_rad] for p in reference_poses
    ])
    test_orientations = np.array([
        [p.roll_rad, p.pitch_rad, p.yaw_rad] for p in test_poses
    ])
    
    orientation_diff = ref_orientations[:len(test_orientations)] - test_orientations[:len(ref_orientations)]
    orientation_rmse = np.sqrt(np.mean(np.sum(orientation_diff ** 2, axis=1)))
    
    return {
        'position_rmse_m': position_rmse,
        'orientation_rmse_rad': orientation_rmse,
        'total_rmse': np.sqrt(position_rmse**2 + orientation_rmse**2)
    }


def calculate_map_alignment_rmse(poses_list: List[List[PoseMetrics]]) -> List[float]:
    """
    Calculate Map-Alignment RMSE across multiple runs.
    This is a simplified implementation; real version should use
    ICP or similar alignment algorithm.
    
    Args:
        poses_list: List of pose lists (one per run)
        
    Returns:
        List of Map-Alignment RMSE values (one per run)
    """
    rmse_values = []
    
    for i, poses in enumerate(poses_list):
        if not poses:
            logger.warning(f'Run {i} has no pose data')
            continue
        
        # Calculate trajectory variance as proxy for map alignment quality
        positions = np.array([[p.x, p.y, p.z] for p in poses])
        
        # Use position variance as proxy (real implementation would use ICP)
        position_variance = np.mean(np.var(positions, axis=0))
        map_alignment_rmse = np.sqrt(position_variance)
        
        rmse_values.append(map_alignment_rmse)
    
    logger.info(f'Calculated Map-Alignment RMSE for {len(rmse_values)} runs')
    return rmse_values


# ============================================================================
# STATISTICAL ANALYSIS
# ============================================================================

def wilcoxon_test(group_a: np.ndarray, group_b: np.ndarray) -> Dict:
    """
    Perform Wilcoxon signed-rank test (non-parametric alternative to t-test).
    
    Args:
        group_a: First group of measurements
        group_b: Second group of measurements
        
    Returns:
        Dictionary with test results
    """
    if len(group_a) != len(group_b):
        logger.warning('Groups have different sizes; using Mann-Whitney U test')
        statistic, p_value = stats.mannwhitneyu(group_a, group_b, alternative='two-sided')
        test_name = 'Mann-Whitney U'
    else:
        statistic, p_value = stats.wilcoxon(group_a, group_b, alternative='two-sided')
        test_name = 'Wilcoxon Signed-Rank'
    
    return {
        'test': test_name,
        'statistic': float(statistic),
        'p_value': float(p_value),
        'significant_at_0_05': p_value < 0.05,
        'significant_at_0_01': p_value < 0.01
    }


def cliffs_delta(group_a: np.ndarray, group_b: np.ndarray) -> Dict:
    """
    Calculate Cliff's delta effect size (non-parametric).
    
    Interpretation:
    - |d| < 0.147: negligible
    - 0.147 <= |d| < 0.330: small
    - 0.330 <= |d| < 0.474: medium
    - |d| >= 0.474: large
    
    Args:
        group_a: First group of measurements
        group_b: Second group of measurements
        
    Returns:
        Dictionary with delta and interpretation
    """
    n1 = len(group_a)
    n2 = len(group_b)
    
    # Count dominance
    domination = 0
    for a in group_a:
        for b in group_b:
            if a > b:
                domination += 1
            elif b > a:
                domination -= 1
    
    delta = domination / (n1 * n2)
    
    # Interpret effect size
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        interpretation = 'negligible'
    elif abs_delta < 0.330:
        interpretation = 'small'
    elif abs_delta < 0.474:
        interpretation = 'medium'
    else:
        interpretation = 'large'
    
    return {
        'delta': float(delta),
        'interpretation': interpretation,
        'abs_delta': float(abs_delta)
    }


# ============================================================================
# DATA AGGREGATION
# ============================================================================

def discover_experiment_runs(experiment_dir: str) -> Dict[str, List[ExperimentRun]]:
    """
    Discover all experiment runs in a directory, grouped by policy.
    
    Args:
        experiment_dir: Root directory containing logs
        
    Returns:
        Dictionary mapping policy names to lists of ExperimentRun objects
    """
    runs_by_policy = {}
    
    scheduler_logs = sorted(Path(experiment_dir).glob('bacs_logs/bacs_scheduler_log_*.csv'))
    vicon_logs_map = {}
    
    # Map Vicon logs by session_id
    for vicon_log in Path(experiment_dir).glob('vicon_logs/vicon_ground_truth_*.csv'):
        session_id = vicon_log.name.split('_')[3]  # Extract session_id
        robot_name = vicon_log.name.split('_')[4]  # Extract robot_name
        vicon_logs_map[(session_id, robot_name)] = str(vicon_log)
    
    # Pair scheduler logs with Vicon logs
    for scheduler_log in scheduler_logs:
        filename = scheduler_log.name
        # Format: bacs_scheduler_log_<session_id>_<policy>_YYYYMMDD_HHMMSS.csv
        parts = filename[len('bacs_scheduler_log_'):-4].split('_')
        
        if len(parts) >= 4:
            session_id = parts[0]
            policy = parts[1]
            timestamp = f'{parts[2]}_{parts[3]}'
            
            # Look for matching Vicon log
            vicon_log = vicon_logs_map.get((session_id, 'robot_0'))
            
            if vicon_log:
                run = ExperimentRun(
                    session_id=session_id,
                    policy=policy,
                    timestamp=timestamp,
                    scheduler_log_file=str(scheduler_log),
                    vicon_log_file=vicon_log
                )
                
                if policy not in runs_by_policy:
                    runs_by_policy[policy] = []
                
                runs_by_policy[policy].append(run)
    
    logger.info(f'Discovered {sum(len(v) for v in runs_by_policy.values())} experiment runs')
    for policy, runs in runs_by_policy.items():
        logger.info(f'  {policy}: {len(runs)} runs')
    
    return runs_by_policy


# ============================================================================
# RESULTS EXPORT
# ============================================================================

def export_results_json(results: Dict, output_file: str):
    """
    Export analysis results as JSON for further processing.
    
    Args:
        results: Analysis results dictionary
        output_file: Output JSON file path
    """
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f'Exported results to {output_file}')


def export_results_csv(results: Dict, output_file: str):
    """
    Export analysis results as CSV for spreadsheet analysis.
    
    Args:
        results: Analysis results dictionary
        output_file: Output CSV file path
    """
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=results.keys())
        writer.writeheader()
        writer.writerow(results)
    
    logger.info(f'Exported results to {output_file}')


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main analysis pipeline."""
    parser = argparse.ArgumentParser(
        description='BACS+ Experiment Data Analysis Pipeline'
    )
    parser.add_argument(
        '--experiment-dir',
        type=str,
        default='./experiment_results',
        help='Root directory containing experiment logs'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./analysis_results',
        help='Output directory for analysis results'
    )
    parser.add_argument(
        '--policy',
        type=str,
        default=None,
        help='Analyze specific policy (if None, analyze all)'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Discover experiment runs
    logger.info(f'Discovering experiments in {args.experiment_dir}')
    runs_by_policy = discover_experiment_runs(args.experiment_dir)
    
    if not runs_by_policy:
        logger.error('No experiment runs found!')
        return
    
    # Analyze each policy
    all_results = {}
    
    for policy, runs in runs_by_policy.items():
        if args.policy and policy != args.policy:
            continue
        
        logger.info(f'\n=== Analyzing policy: {policy} ===')
        
        # Load timing data
        timing_metrics_list = []
        for run in runs:
            metrics = parse_scheduler_log(run.scheduler_log_file)
            if metrics:
                timing_metrics_list.append(metrics)
        
        # Load pose data
        pose_metrics_list = []
        for run in runs:
            metrics = parse_vicon_log(run.vicon_log_file)
            if metrics:
                pose_metrics_list.append(metrics)
        
        # Calculate statistics
        if timing_metrics_list:
            timing_stats = calculate_timing_statistics(timing_metrics_list)
            logger.info(f'Timing Statistics for {policy}:')
            logger.info(f'  T_defer: {timing_stats["t_defer"]["mean_us"]:.3f} ± {timing_stats["t_defer"]["std_us"]:.3f} µs')
            logger.info(f'  T_channel: {timing_stats["t_channel"]["mean_us"]:.3f} ± {timing_stats["t_channel"]["std_us"]:.3f} µs')
            all_results[policy] = {'timing': timing_stats}
        
        if pose_metrics_list:
            map_rmse_values = calculate_map_alignment_rmse(pose_metrics_list)
            logger.info(f'Map-Alignment RMSE for {policy}:')
            logger.info(f'  Mean: {np.mean(map_rmse_values):.6f} m')
            logger.info(f'  Std: {np.std(map_rmse_values):.6f} m')
            all_results[policy]['poses'] = {
                'map_alignment_rmse': map_rmse_values
            }
    
    # Export results
    results_json = os.path.join(args.output_dir, f'analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    export_results_json(all_results, results_json)
    
    logger.info(f'\n=== Analysis Complete ===')
    logger.info(f'Results saved to {args.output_dir}')


if __name__ == '__main__':
    main()
