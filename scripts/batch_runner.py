#!/usr/bin/env python3
"""
Batch Experiment Runner

Automates execution of multiple experiment runs across different policies.

Usage:
    python3 batch_runner.py --policies bacs_plus greedy random --runs 10 --robot-name robot_0
"""

import subprocess
import argparse
import logging
from pathlib import Path
from datetime import datetime
import time


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_experiment(policy: str, session_id: str, robot_name: str,
                   script_path: str, timeout: int = 180) -> bool:
    """
    Execute a single experiment run.
    
    Args:
        policy: Scheduling policy to test
        session_id: Unique session identifier
        robot_name: Robot identifier
        script_path: Path to orchestration script
        timeout: Execution timeout in seconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f'Starting experiment: policy={policy}, session={session_id}')
        
        cmd = [
            'bash',
            script_path,
            policy,
            session_id,
            robot_name
        ]
        
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=False
        )
        
        if result.returncode == 0:
            logger.info(f'Experiment completed successfully: {session_id}')
            return True
        else:
            logger.error(f'Experiment failed with return code {result.returncode}')
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f'Experiment timed out after {timeout}s')
        return False
    except Exception as e:
        logger.error(f'Error running experiment: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Batch Experiment Runner for BACS+ Scheduler'
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
    parser.add_argument(
        '--robot-name',
        type=str,
        default='robot_0',
        help='Robot identifier'
    )
    parser.add_argument(
        '--script-path',
        type=str,
        default='ros2_ws/src/bacs_scheduler/scripts/run_physical_session.sh',
        help='Path to orchestration script'
    )
    parser.add_argument(
        '--delay-between-runs',
        type=int,
        default=30,
        help='Delay between runs in seconds'
    )
    
    args = parser.parse_args()
    
    # Verify script exists
    if not Path(args.script_path).exists():
        logger.error(f'Script not found: {args.script_path}')
        return
    
    # Execute batch runs
    start_time = datetime.now()
    logger.info(f'=== BACS+ Batch Experiment Runner ===')
    logger.info(f'Policies: {args.policies}')
    logger.info(f'Runs per policy: {args.runs}')
    logger.info(f'Start time: {start_time}')
    
    total_runs = len(args.policies) * args.runs
    completed_runs = 0
    failed_runs = 0
    
    for policy in args.policies:
        for run_idx in range(1, args.runs + 1):
            session_id = f'{policy}_run{run_idx:02d}_{datetime.now().strftime("%Y%m%d")}
            
            success = run_experiment(
                policy=policy,
                session_id=session_id,
                robot_name=args.robot_name,
                script_path=args.script_path
            )
            
            if success:
                completed_runs += 1
            else:
                failed_runs += 1
            
            # Progress report
            progress = completed_runs + failed_runs
            logger.info(
                f'Progress: {progress}/{total_runs} '
                f'(Completed: {completed_runs}, Failed: {failed_runs})'
            )
            
            # Delay between runs
            if progress < total_runs:
                logger.info(f'Waiting {args.delay_between_runs}s before next run...')
                time.sleep(args.delay_between_runs)
    
    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() / 60.0
    
    logger.info(f'\n=== Batch Execution Summary ===')
    logger.info(f'Total runs: {total_runs}')
    logger.info(f'Completed: {completed_runs}')
    logger.info(f'Failed: {failed_runs}')
    logger.info(f'Success rate: {100 * completed_runs / total_runs:.1f}%')
    logger.info(f'Total duration: {duration:.1f} minutes')
    logger.info(f'End time: {end_time}')


if __name__ == '__main__':
    main()
