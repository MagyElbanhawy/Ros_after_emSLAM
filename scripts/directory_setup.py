#!/usr/bin/env python3
"""
Experiment Results Directory Manager

Creates organized directory structure for storing experimental results.
"""

import os
from pathlib import Path
from datetime import datetime


def create_experiment_structure(base_dir: str = './experiment_results') -> dict:
    """
    Create organized directory structure for experiment results.
    
    Structure:
        experiment_results/
        ├── bacs_logs/              # Scheduler logs (timing data)
        ├── vicon_logs/             # Ground truth pose logs
        ├── rosbags/                # ROS 2 bag recordings
        ├── analysis_results/       # Statistical analysis output
        ├── figures/                # Publication-ready figures
        ├── raw_data/               # Raw CSV exports
        └── metadata/               # Experiment metadata
    
    Args:
        base_dir: Root directory for experiment results
        
    Returns:
        Dictionary mapping directory names to paths
    """
    directories = {
        'base': base_dir,
        'bacs_logs': os.path.join(base_dir, 'bacs_logs'),
        'vicon_logs': os.path.join(base_dir, 'vicon_logs'),
        'rosbags': os.path.join(base_dir, 'rosbags'),
        'analysis_results': os.path.join(base_dir, 'analysis_results'),
        'figures': os.path.join(base_dir, 'figures'),
        'raw_data': os.path.join(base_dir, 'raw_data'),
        'metadata': os.path.join(base_dir, 'metadata'),
    }
    
    # Create all directories
    for dir_path in directories.values():
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f'✓ Created: {dir_path}')
    
    return directories


def create_experiment_manifest(base_dir: str, policies: list, runs_per_policy: int):
    """
    Create experiment manifest file with metadata.
    
    Args:
        base_dir: Root directory for experiment results
        policies: List of policies to test
        runs_per_policy: Number of runs per policy
    """
    manifest_file = os.path.join(base_dir, 'metadata', 'experiment_manifest.txt')
    
    with open(manifest_file, 'w') as f:
        f.write('BACS+ Scheduler Experiment Manifest\n')
        f.write('=' * 60 + '\n\n')
        
        f.write(f'Created: {datetime.now().isoformat()}\n')
        f.write(f'Total Experiments: {len(policies) * runs_per_policy}\n')
        f.write(f'Policies: {[", ".join(policies)]}\n')
        f.write(f'Runs per Policy: {runs_per_policy}\n\n')
        
        f.write('Directory Structure:\n')
        f.write('  bacs_logs/          - Scheduler latency measurements\n')
        f.write('  vicon_logs/         - Ground truth pose data\n')
        f.write('  rosbags/            - ROS 2 message recordings\n')
        f.write('  analysis_results/   - Statistical analysis output\n')
        f.write('  figures/            - Publication figures\n')
        f.write('  raw_data/           - Processed CSV exports\n')
        f.write('  metadata/           - Experiment configuration\n\n')
        
        f.write('Key Files:\n')
        f.write('  bacs_scheduler_log_<session>_<policy>_YYYYMMDD_HHMMSS.csv\n')
        f.write('    Columns: seq_id, t_gen_ns, t_selected_ns, t_tx_ns, t_rx_ns, selected_policy, constraint_count\n')
        f.write('    Metrics: T_defer = t_selected_ns - t_gen_ns\n')
        f.write('             T_channel = t_rx_ns - t_tx_ns\n\n')
        
        f.write('  vicon_ground_truth_<session>_<robot>_YYYYMMDD_HHMMSS.csv\n')
        f.write('    Columns: timestamp_ns, x, y, z, roll_rad, pitch_rad, yaw_rad, vx, vy, vz\n')
        f.write('    Use for: Map-Alignment RMSE, Pose RMSE calculations\n')
    
    print(f'✓ Created manifest: {manifest_file}')


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Create experiment results directory structure'
    )
    parser.add_argument(
        '--base-dir',
        type=str,
        default='./experiment_results',
        help='Base directory for experiment results'
    )
    parser.add_argument(
        '--policies',
        nargs='+',
        default=['bacs_plus', 'greedy', 'random'],
        help='List of policies to test'
    )
    parser.add_argument(
        '--runs',
        type=int,
        default=10,
        help='Number of runs per policy'
    )
    
    args = parser.parse_args()
    
    print('Creating experiment results structure...')
    dirs = create_experiment_structure(args.base_dir)
    print(f'\n✓ Base directory: {args.base_dir}\n')
    
    create_experiment_manifest(args.base_dir, args.policies, args.runs)
    print(f'\n✓ All directories created successfully!')
