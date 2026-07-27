#!/usr/bin/env python3
"""
Quick Integration Test

Verifies that all components work together end-to-end:
1. Generate mock data
2. Run analysis pipeline
3. Verify outputs

Usage:
    python3 scripts/integration_test.py
"""

import subprocess
import sys
import os
from pathlib import Path
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_command(cmd, description):
    """
    Execute a command and report results.
    
    Args:
        cmd: Command to run (list)
        description: Description of what's happening
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f'\n{'='*70}')
    logger.info(f'{description}')
    logger.info(f'{'='*70}')
    logger.info(f'Command: {" ".join(cmd)}')
    
    try:
        result = subprocess.run(cmd, capture_output=False, timeout=300)
        if result.returncode == 0:
            logger.info(f'✓ {description} - SUCCESS')
            return True
        else:
            logger.error(f'✗ {description} - FAILED (exit code {result.returncode})')
            return False
    except subprocess.TimeoutExpired:
        logger.error(f'✗ {description} - TIMEOUT')
        return False
    except Exception as e:
        logger.error(f'✗ {description} - ERROR: {e}')
        return False


def check_output_files(output_dir):
    """
    Verify that expected output files exist.
    
    Args:
        output_dir: Directory to check
        
    Returns:
        True if all files present, False otherwise
    """
    logger.info(f'\n{'='*70}')
    logger.info('Checking Output Files')
    logger.info(f'{'='*70}')
    
    checks = [
        ('Scheduler logs', os.path.join(output_dir, 'bacs_logs')),
        ('Vicon logs', os.path.join(output_dir, 'vicon_logs')),
        ('Analysis results', os.path.join(output_dir, 'analysis_results')),
    ]
    
    all_ok = True
    for check_name, path in checks:
        if Path(path).exists():
            file_count = len(list(Path(path).glob('*')))
            logger.info(f'✓ {check_name}: {path} ({file_count} files)')
        else:
            logger.error(f'✗ {check_name}: {path} - NOT FOUND')
            all_ok = False
    
    return all_ok


def preview_csv_files(output_dir):
    """
    Show preview of generated CSV files.
    
    Args:
        output_dir: Directory containing CSVs
    """
    logger.info(f'\n{'='*70}')
    logger.info('CSV File Previews')
    logger.info(f'{'='*70}')
    
    # Preview scheduler log
    scheduler_logs = list(Path(output_dir).glob('bacs_logs/bacs_scheduler_log_*.csv'))
    if scheduler_logs:
        scheduler_log = scheduler_logs[0]
        logger.info(f'\n[Scheduler Log Sample] {scheduler_log.name}')
        with open(scheduler_log, 'r') as f:
            for i, line in enumerate(f):
                if i < 3:  # Header + 2 data rows
                    logger.info(f'  {line.rstrip()}')
                else:
                    break
    
    # Preview Vicon log
    vicon_logs = list(Path(output_dir).glob('vicon_logs/vicon_ground_truth_*.csv'))
    if vicon_logs:
        vicon_log = vicon_logs[0]
        logger.info(f'\n[Vicon Log Sample] {vicon_log.name}')
        with open(vicon_log, 'r') as f:
            for i, line in enumerate(f):
                if i < 3:  # Header + 2 data rows
                    logger.info(f'  {line.rstrip()}')
                else:
                    break


def preview_analysis_results(output_dir):
    """
    Show preview of analysis results.
    
    Args:
        output_dir: Directory containing analysis_results
    """
    logger.info(f'\n{'='*70}')
    logger.info('Analysis Results Preview')
    logger.info(f'{'='*70}')
    
    json_files = list(Path(output_dir).glob('analysis_results/analysis_results_*.json'))
    if json_files:
        json_file = json_files[-1]  # Latest file
        logger.info(f'\n[Analysis Results] {json_file.name}')
        try:
            with open(json_file, 'r') as f:
                results = json.load(f)
            
            for policy, data in results.items():
                if 'timing' in data:
                    timing = data['timing']
                    logger.info(f'\n  Policy: {policy}')
                    logger.info(f'    T_defer:')
                    logger.info(f'      Mean: {timing["t_defer"]["mean_us"]:.2f} ± {timing["t_defer"]["std_us"]:.2f} µs')
                    logger.info(f'      Median: {timing["t_defer"]["median_us"]:.2f} µs')
                    logger.info(f'      P95: {timing["t_defer"]["p95_us"]:.2f} µs')
                    logger.info(f'    T_channel:')
                    logger.info(f'      Mean: {timing["t_channel"]["mean_us"]:.2f} ± {timing["t_channel"]["std_us"]:.2f} µs')
                    logger.info(f'    Sample count: {timing["sample_count"]}')
        except Exception as e:
            logger.error(f'Error reading analysis results: {e}')
    else:
        logger.warning('No analysis results found')


def main():
    logger.info('\n' + '='*70)
    logger.info('BACS+ Integration Test - Mock Data → Analysis Pipeline')
    logger.info('='*70)
    
    # Setup
    output_dir = './experiment_results_test'
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Step 1: Generate mock data
    success = run_command(
        ['python3', 'scripts/generate_mock_data.py',
         '--output-dir', output_dir,
         '--policies', 'bacs_plus', 'greedy', 'random',
         '--runs', '5',  # Use 5 runs for faster testing
         '--constraints-per-run', '100'],
        'Step 1: Generate Mock Data'
    )
    if not success:
        logger.error('Failed to generate mock data')
        sys.exit(1)
    
    # Step 2: Run analysis pipeline
    success = run_command(
        ['python3', 'scripts/analysis_pipeline.py',
         '--experiment-dir', output_dir,
         '--output-dir', os.path.join(output_dir, 'analysis_results')],
        'Step 2: Run Analysis Pipeline'
    )
    if not success:
        logger.error('Failed to run analysis pipeline')
        sys.exit(1)
    
    # Step 3: Verify outputs
    if not check_output_files(output_dir):
        logger.error('Output file validation failed')
        sys.exit(1)
    
    # Step 4: Show previews
    preview_csv_files(output_dir)
    preview_analysis_results(output_dir)
    
    # Summary
    logger.info(f'\n' + '='*70)
    logger.info('Integration Test Complete - All Steps Successful!')
    logger.info('='*70)
    logger.info(f'\nTest results saved to: {output_dir}')
    logger.info(f'\nYou can now:')
    logger.info(f'  1. Review CSV files:')
    logger.info(f'     head {output_dir}/bacs_logs/bacs_scheduler_log_*.csv')
    logger.info(f'\n  2. Review analysis results:')
    logger.info(f'     cat {output_dir}/analysis_results/analysis_results_*.json | python3 -m json.tool')
    logger.info(f'\n  3. Run full integration test with more samples:')
    logger.info(f'     python3 scripts/generate_mock_data.py --runs 10 --constraints-per-run 1000')
    logger.info()


if __name__ == '__main__':
    main()
