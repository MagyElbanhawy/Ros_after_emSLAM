#!/bin/bash

################################################################################
# Quick Start: Complete Pipeline Test (Mock Data)
#
# This script runs the ENTIRE pipeline end-to-end:
#   1. Generate realistic mock CSV data
#   2. Run statistical analysis
#   3. Display results
#
# Usage:
#   bash scripts/run_full_test.sh
#
# Expected output: CSV files + analysis results in 2-3 minutes
################################################################################

set -e

echo ""
echo "================================================================================"
echo "BACS+ Complete Pipeline Test - Mock Data to Analysis"
echo "================================================================================"
echo ""

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR="./experiment_results"
OUTPUT_DIR="${BASE_DIR}_test"
SCRIPTS_DIR="./scripts"

echo "[INFO] Configuration:"
echo "  Base directory: $BASE_DIR"
echo "  Test directory: $OUTPUT_DIR"
echo ""

# ============================================================================
# Step 1: Generate Mock Data
# ============================================================================

echo "================================================================================"
echo "STEP 1: Generate Mock CSV Data (30 files - 3 policies × 10 runs)"
echo "================================================================================"
echo ""

echo "[INFO] Generating realistic mock data..."
python3 $SCRIPTS_DIR/generate_mock_data.py \
  --output-dir $OUTPUT_DIR \
  --policies bacs_plus greedy random \
  --runs 10 \
  --constraints-per-run 100

echo ""
echo "[SUCCESS] Mock data generation complete!"
echo ""

# ============================================================================
# Step 2: Verify Generated Files
# ============================================================================

echo "================================================================================"
echo "STEP 2: Verify Generated CSV Files"
echo "================================================================================"
echo ""

echo "[INFO] Scheduler logs (Timing Data):"
ls -lh $OUTPUT_DIR/bacs_logs/ | tail -5
echo "  Total: $(ls -1 $OUTPUT_DIR/bacs_logs/*.csv | wc -l) files"
echo ""

echo "[INFO] Vicon logs (Ground Truth Poses):"
ls -lh $OUTPUT_DIR/vicon_logs/ | tail -5
echo "  Total: $(ls -1 $OUTPUT_DIR/vicon_logs/*.csv | wc -l) files"
echo ""

# ============================================================================
# Step 3: Preview CSV Content
# ============================================================================

echo "================================================================================"
echo "STEP 3: Preview CSV File Contents"
echo "================================================================================"
echo ""

echo "[INFO] Scheduler Log Sample (T_defer, T_channel):"
echo ""
head -3 $OUTPUT_DIR/bacs_logs/bacs_scheduler_log_*.csv 2>/dev/null | head -3
echo "  ..."
echo ""

echo "[INFO] Vicon Log Sample (Poses):"
echo ""
head -3 $OUTPUT_DIR/vicon_logs/vicon_ground_truth_*.csv 2>/dev/null | head -3
echo "  ..."
echo ""

# ============================================================================
# Step 4: Run Analysis Pipeline
# ============================================================================

echo "================================================================================"
echo "STEP 4: Run Statistical Analysis Pipeline"
echo "================================================================================"
echo ""

echo "[INFO] Analyzing timing and pose metrics..."
python3 $SCRIPTS_DIR/analysis_pipeline.py \
  --experiment-dir $OUTPUT_DIR \
  --output-dir $OUTPUT_DIR/analysis_results

echo ""
echo "[SUCCESS] Analysis complete!"
echo ""

# ============================================================================
# Step 5: Display Results
# ============================================================================

echo "================================================================================"
echo "STEP 5: Analysis Results Summary"
echo "================================================================================"
echo ""

echo "[INFO] Checking analysis output files..."
if [ -d "$OUTPUT_DIR/analysis_results" ]; then
    JSON_FILE=$(ls -t $OUTPUT_DIR/analysis_results/*.json 2>/dev/null | head -1)
    if [ -f "$JSON_FILE" ]; then
        echo "  Found: $(basename $JSON_FILE)"
        echo ""
        echo "[INFO] Key Results (Pretty-printed JSON):"
        python3 -c "
import json
with open('$JSON_FILE', 'r') as f:
    data = json.load(f)
    for policy, results in data.items():
        print(f'\n  {policy}:')
        if 'timing' in results:
            timing = results['timing']
            print(f'    T_defer:')
            print(f'      Mean: {timing[\"t_defer\"][\"mean_us\"]:.2f} ± {timing[\"t_defer\"][\"std_us\"]:.2f} µs')
            print(f'      Median: {timing[\"t_defer\"][\"median_us\"]:.2f} µs')
            print(f'      P95: {timing[\"t_defer\"][\"p95_us\"]:.2f} µs')
            print(f'    T_channel:')
            print(f'      Mean: {timing[\"t_channel\"][\"mean_us\"]:.2f} ± {timing[\"t_channel\"][\"std_us\"]:.2f} µs')
            print(f'    Samples: {timing[\"sample_count\"]}')
"
        echo ""
    else
        echo "  ERROR: No JSON results found"
    fi
else
    echo "  ERROR: Analysis results directory not found"
fi

echo ""

# ============================================================================
# Step 6: Summary & Next Steps
# ============================================================================

echo "================================================================================"
echo "PIPELINE TEST COMPLETE"
echo "================================================================================"
echo ""

echo "✓ Generated CSV Files:"
echo "  Scheduler logs (T_defer, T_channel): $OUTPUT_DIR/bacs_logs/"
echo "  Vicon logs (Poses): $OUTPUT_DIR/vicon_logs/"
echo ""

echo "✓ Analysis Results:"
echo "  JSON output: $OUTPUT_DIR/analysis_results/"
echo ""

echo "Next Steps:"
echo "  1. Review CSV files:"
echo "     cat $OUTPUT_DIR/bacs_logs/bacs_scheduler_log_*.csv | head -20"
echo ""
echo "  2. Inspect full analysis results:"
echo "     python3 -m json.tool $OUTPUT_DIR/analysis_results/analysis_results_*.json"
echo ""
echo "  3. Run full integration test:"
echo "     python3 scripts/integration_test.py"
echo ""
echo "  4. When ready for real hardware experiments:"
echo "     bash ros2_ws/src/bacs_scheduler/scripts/run_physical_session.sh bacs_plus session_001 robot_0"
echo ""
echo "================================================================================"
echo ""
