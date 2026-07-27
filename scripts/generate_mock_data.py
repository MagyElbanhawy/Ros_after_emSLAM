#!/usr/bin/env python3
"""
Mock Data Generator for BACS+ Experiments

Generates realistic simulated CSV files for testing the analysis pipeline
without running actual hardware experiments.

Usage:
    python3 scripts/generate_mock_data.py \
      --output-dir ./experiment_results \
      --policies bacs_plus greedy random \
      --runs 10 \
      --constraints-per-run 100
"""

import os
import csv
import argparse
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_scheduler_log(output_file: str, policy: str, num_constraints: int = 100):
    """
    Generate realistic scheduler log with timing data.
    
    Args:
        output_file: Path to output CSV file
        policy: Scheduling policy (bacs_plus, greedy, random)
        num_constraints: Number of constraints to simulate
    """
    # Latency profiles for different policies (in microseconds)
    latency_profiles = {
        'bacs_plus': {
            't_defer_mean': 150,
            't_defer_std': 45,
            't_channel_mean': 5250,
            't_channel_std': 1200
        },
        'greedy': {
            't_defer_mean': 285,
            't_defer_std': 95,
            't_channel_mean': 5400,
            't_channel_std': 1300
        },
        'random': {
            't_defer_mean': 420,
            't_defer_std': 150,
            't_channel_mean': 5600,
            't_channel_std': 1500
        }
    }
    
    profile = latency_profiles.get(policy, latency_profiles['bacs_plus'])
    
    # Base timestamp (120 seconds worth of nanoseconds)
    base_ns = int(datetime.now().timestamp() * 1e9)
    constraint_interval_ns = int(120e9 / num_constraints)  # Spread over 120 seconds
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'seq_id',
                't_gen_ns',
                't_selected_ns',
                't_tx_ns',
                't_rx_ns',
                'selected_policy',
                'constraint_count'
            ]
        )
        writer.writeheader()
        
        for seq_id in range(num_constraints):
            # Generation time (evenly spaced)
            t_gen_ns = base_ns + seq_id * constraint_interval_ns
            
            # Selection latency (T_defer in ns)
            t_defer_us = np.random.normal(
                profile['t_defer_mean'],
                profile['t_defer_std']
            )
            t_defer_ns = int(max(50, t_defer_us) * 1000)  # Clamp to minimum
            t_selected_ns = t_gen_ns + t_defer_ns
            
            # Transmission (small delay ~1 microsecond)
            t_tx_ns = t_selected_ns + int(np.random.uniform(500, 1500) * 1000)
            
            # Channel latency (T_channel in ns)
            t_channel_us = np.random.normal(
                profile['t_channel_mean'],
                profile['t_channel_std']
            )
            t_channel_ns = int(max(2000, t_channel_us) * 1000)  # Clamp to minimum
            t_rx_ns = t_tx_ns + t_channel_ns
            
            writer.writerow({
                'seq_id': seq_id,
                't_gen_ns': t_gen_ns,
                't_selected_ns': t_selected_ns,
                't_tx_ns': t_tx_ns,
                't_rx_ns': t_rx_ns,
                'selected_policy': policy,
                'constraint_count': seq_id + 1
            })
    
    logger.info(f'Generated scheduler log: {output_file} ({num_constraints} constraints)')


def generate_vicon_log(output_file: str, session_id: str, robot_name: str,
                       num_samples: int = 2400):
    """
    Generate realistic Vicon ground truth log with pose data.
    
    Simulates a circular trajectory at 0.5 m/s over 120 seconds.
    
    Args:
        output_file: Path to output CSV file
        session_id: Session identifier
        robot_name: Robot identifier
        num_samples: Number of pose samples (20 Hz = 2400 for 120s)
    """
    # Trajectory parameters
    radius = 1.0  # meters
    speed = 0.5   # m/s
    duration_s = 120.0  # seconds
    sample_rate_hz = 20  # Hz
    
    base_ns = int(datetime.now().timestamp() * 1e9)
    dt_ns = int((1.0 / sample_rate_hz) * 1e9)
    
    # Generate circular trajectory
    t_values = np.linspace(0, duration_s, num_samples)
    angle_values = (speed / radius) * t_values  # Angular velocity
    
    # Add noise for realism
    position_noise = 0.005  # 5mm noise
    orientation_noise = 0.01  # 0.01 rad noise
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                'timestamp_ns',
                'x',
                'y',
                'z',
                'roll_rad',
                'pitch_rad',
                'yaw_rad',
                'vx',
                'vy',
                'vz'
            ]
        )
        writer.writeheader()
        
        for i, (t, angle) in enumerate(zip(t_values, angle_values)):
            timestamp_ns = base_ns + i * dt_ns
            
            # Circular motion
            x = radius * np.cos(angle) + np.random.normal(0, position_noise)
            y = radius * np.sin(angle) + np.random.normal(0, position_noise)
            z = 0.1 + np.random.normal(0, position_noise)  # 10cm height
            
            # Orientation (pointing tangent to circle)
            yaw = angle + np.pi/2 + np.random.normal(0, orientation_noise)
            roll = np.random.normal(0, orientation_noise)
            pitch = np.random.normal(0, orientation_noise)
            
            # Velocity (tangent to circle)
            vx = -speed * np.sin(angle) + np.random.normal(0, 0.01)
            vy = speed * np.cos(angle) + np.random.normal(0, 0.01)
            vz = np.random.normal(0, 0.001)
            
            writer.writerow({
                'timestamp_ns': timestamp_ns,
                'x': f'{x:.6f}',
                'y': f'{y:.6f}',
                'z': f'{z:.6f}',
                'roll_rad': f'{roll:.6f}',
                'pitch_rad': f'{pitch:.6f}',
                'yaw_rad': f'{yaw:.6f}',
                'vx': f'{vx:.6f}',
                'vy': f'{vy:.6f}',
                'vz': f'{vz:.6f}'
            })
    
    logger.info(f'Generated Vicon log: {output_file} ({num_samples} samples @ {sample_rate_hz}Hz)')


def generate_mock_dataset(output_dir: str, policies: list, runs_per_policy: int,
                         constraints_per_run: int = 100):
    """
    Generate complete mock dataset for all policies and runs.
    
    Args:
        output_dir: Base output directory
        policies: List of policies to simulate
        runs_per_policy: Number of runs per policy
        constraints_per_run: Number of constraints per run
    """
    # Create directories
    bacs_logs_dir = os.path.join(output_dir, 'bacs_logs')
    vicon_logs_dir = os.path.join(output_dir, 'vicon_logs')
    
    Path(bacs_logs_dir).mkdir(parents=True, exist_ok=True)
    Path(vicon_logs_dir).mkdir(parents=True, exist_ok=True)
    
    total_files = len(policies) * runs_per_policy * 2  # 2 files per run
    file_count = 0
    
    logger.info(f'Generating {total_files} mock CSV files...')
    logger.info(f'Policies: {policies}')
    logger.info(f'Runs per policy: {runs_per_policy}')
    logger.info(f'Constraints per run: {constraints_per_run}\n')
    
    for policy in policies:
        for run_idx in range(1, runs_per_policy + 1):
            # Create filenames
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            session_id = f'{policy}_run{run_idx:02d}'
            robot_name = 'robot_0'
            
            # Generate scheduler log
            scheduler_log = os.path.join(
                bacs_logs_dir,
                f'bacs_scheduler_log_{session_id}_{timestamp}.csv'
            )
            generate_scheduler_log(
                scheduler_log,
                policy=policy,
                num_constraints=constraints_per_run
            )
            file_count += 1
            
            # Generate Vicon log
            vicon_log = os.path.join(
                vicon_logs_dir,
                f'vicon_ground_truth_{session_id}_{robot_name}_{timestamp}.csv'
            )
            generate_vicon_log(
                vicon_log,
                session_id=session_id,
                robot_name=robot_name,
                num_samples=2400  # 20 Hz for 120 seconds
            )
            file_count += 1
            
            progress_pct = 100 * file_count / total_files
            logger.info(f'Progress: {file_count}/{total_files} ({progress_pct:.0f}%)')
    
    logger.info(f'\n✓ Generated {file_count} files in {output_dir}')
    return file_count


def main():
    parser = argparse.ArgumentParser(
        description='Generate mock BACS+ experiment data for testing'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./experiment_results',
        help='Output directory for mock CSV files'
    )
    parser.add_argument(
        '--policies',
        nargs='+',
        default=['bacs_plus', 'greedy', 'random'],
        help='List of policies to simulate'
    )
    parser.add_argument(
        '--runs',
        type=int,
        default=10,
        help='Number of runs per policy'
    )
    parser.add_argument(
        '--constraints-per-run',
        type=int,
        default=100,
        help='Number of constraints per run'
    )
    
    args = parser.parse_args()
    
    print('\n' + '='*70)
    print('BACS+ Mock Data Generator')
    print('='*70 + '\n')
    
    file_count = generate_mock_dataset(
        output_dir=args.output_dir,
        policies=args.policies,
        runs_per_policy=args.runs,
        constraints_per_run=args.constraints_per_run
    )
    
    print(f'\n✓ All mock data generated successfully!')
    print(f'\nNext steps:')
    print(f'  1. Analyze results:')
    print(f'     python3 scripts/analysis_pipeline.py --experiment-dir {args.output_dir}')
    print(f'\n  2. Check outputs:')
    print(f'     ls -lh {args.output_dir}/bacs_logs/')
    print(f'     ls -lh {args.output_dir}/vicon_logs/')
    print(f'\n  3. Preview CSV files:')
    print(f'     head {args.output_dir}/bacs_logs/bacs_scheduler_log_*.csv')
    print(f'     head {args.output_dir}/vicon_logs/vicon_ground_truth_*.csv')
    print()


if __name__ == '__main__':
    main()
