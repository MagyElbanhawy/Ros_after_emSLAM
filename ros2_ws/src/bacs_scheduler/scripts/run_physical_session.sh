#!/bin/bash

################################################################################
# Physical Experiment Orchestrator for BACS+ Scheduler
#
# This script automates a single 120-second experimental run, handling:
#   1. ROS 2 environment setup
#   2. Scheduler node launch with specific policy
#   3. Vicon logger initialization
#   4. Bag recording (optional)
#   5. Policy execution
#   6. Clean shutdown and log collection
#
# DO NOT rely on manual ros2 run commands—human timing error will ruin
# T_defer measurements. This script ensures deterministic, reproducible runs.
#
# Usage:
#   bash run_physical_session.sh [policy_name] [session_id] [robot_name]
#
# Examples:
#   bash run_physical_session.sh bacs_plus session_001 robot_0
#   bash run_physical_session.sh greedy session_001 robot_0
#   bash run_physical_session.sh random session_001 robot_0
#
# Output:
#   - bacs_logs/bacs_scheduler_log_<session>_<policy>_YYYYMMDD_HHMMSS.csv
#   - vicon_logs/vicon_ground_truth_<session>_<robot>_YYYYMMDD_HHMMSS.csv
#   - rosbags/<session>_<policy>_YYYYMMDD_HHMMSS.db3
#
################################################################################

set -e  # Exit on error

# ============================================================================
# CONFIGURATION
# ============================================================================

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_DIR="$(dirname "$(dirname "$(dirname "$SCRIPT_DIR"))")"  # ros2_ws

# Default parameters (can be overridden by command-line arguments)
POLICY="${1:-bacs_plus}"
SESSION_ID="${2:-default_session}"
ROBOT_NAME="${3:-robot_0}"

# Experiment duration (seconds)
EXPERIMENT_DURATION=120

# Log directories
BACS_LOG_DIR="${WS_DIR}/bacs_logs"
VICON_LOG_DIR="${WS_DIR}/vicon_logs"
ROSBAG_DIR="${WS_DIR}/rosbags"

# Create output directories
mkdir -p "$BACS_LOG_DIR"
mkdir -p "$VICON_LOG_DIR"
mkdir -p "$ROSBAG_DIR"

# Timestamp for file naming
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ============================================================================
# LOGGING AND UTILITIES
# ============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

log_info "=== BACS+ Physical Experiment Orchestrator ==="
log_info "Policy: $POLICY"
log_info "Session ID: $SESSION_ID"
log_info "Robot Name: $ROBOT_NAME"
log_info "Experiment Duration: ${EXPERIMENT_DURATION}s"
log_info "Workspace: $WS_DIR"

# Check if ROS 2 is sourced
if [ -z "$ROS_DISTRO" ]; then
    log_error "ROS 2 environment not sourced. Please source setup.bash"
    exit 1
fi

log_info "ROS 2 Distribution: $ROS_DISTRO"

# Check if package is built
if [ ! -d "$WS_DIR/install/bacs_scheduler" ]; then
    log_warning "bacs_scheduler not built. Attempting build..."
    cd "$WS_DIR"
    colcon build --symlink-install --packages-select bacs_scheduler
    if [ $? -ne 0 ]; then
        log_error "Build failed. Exiting."
        exit 1
    fi
    log_success "Build completed"
fi

# Source install space
source "$WS_DIR/install/setup.bash"

# ============================================================================
# START BACKGROUND NODES
# ============================================================================

log_info "Starting ROS 2 daemon..."
ros2 daemon start 2>/dev/null || true

# Store PIDs for cleanup
declare -a PIDS

# Function to cleanup on exit
cleanup() {
    log_info "Cleaning up..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Terminating process $pid"
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    # Give processes time to terminate gracefully
    sleep 2
    # Force kill any remaining processes
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    log_success "Cleanup completed"
}

# Register cleanup function
trap cleanup EXIT

# ============================================================================
# START EXPERIMENT
# ============================================================================

log_info ""
log_info "=== Starting Experiment ==="
log_info "Launching scheduler node with policy: $POLICY"

# Launch BACS Scheduler Node
ros2 run bacs_scheduler bacs_scheduler_node \
    --ros-args \
    -p session_id:="$SESSION_ID" \
    -p policy:="$POLICY" \
    -p log_dir:="$BACS_LOG_DIR" \
    > /tmp/bacs_scheduler_${TIMESTAMP}.log 2>&1 &
SCHEDULER_PID=$!
PIDS+=(${SCHEDULER_PID})

log_info "Scheduler PID: $SCHEDULER_PID"
sleep 2  # Give node time to initialize

# Launch Vicon Logger Node
log_info "Launching Vicon logger node"
ros2 run bacs_scheduler vicon_logger_node \
    --ros-args \
    -p session_id:="$SESSION_ID" \
    -p robot_name:="$ROBOT_NAME" \
    -p log_dir:="$VICON_LOG_DIR" \
    > /tmp/vicon_logger_${TIMESTAMP}.log 2>&1 &
VICON_PID=$!
PIDS+=(${VICON_PID})

log_info "Vicon Logger PID: $VICON_PID"
sleep 2  # Give node time to initialize

# Start ROS 2 bag recording (optional)
log_info "Starting ROS 2 bag recording"
ROSBAG_FILE="$ROSBAG_DIR/${SESSION_ID}_${POLICY}_${TIMESTAMP}"
ros2 bag record -a -o "$ROSBAG_FILE" \
    > /tmp/rosbag_${TIMESTAMP}.log 2>&1 &
ROSBAG_PID=$!
PIDS+=(${ROSBAG_PID})

log_info "ROS 2 Bag Recording PID: $ROSBAG_PID"

# ============================================================================
# EXPERIMENT EXECUTION
# ============================================================================

log_info ""
log_info "=== Experiment Running ==="
log_info "Duration: ${EXPERIMENT_DURATION} seconds"
log_info "Start time: $(date)"

# Run experiment for specified duration
for ((i=1; i<=EXPERIMENT_DURATION; i++)); do
    elapsed=$i
    remaining=$((EXPERIMENT_DURATION - i))
    
    # Print progress every 10 seconds
    if [ $((i % 10)) -eq 0 ]; then
        log_info "Progress: ${elapsed}s / ${EXPERIMENT_DURATION}s (${remaining}s remaining)"
    fi
    
    sleep 1
done

log_success "Experiment completed at $(date)"

# ============================================================================
# SHUTDOWN
# ============================================================================

log_info ""
log_info "=== Shutting Down ==="

# Stop bag recording first (gracefully)
log_info "Stopping bag recording..."
kill -TERM $ROSBAG_PID 2>/dev/null || true
sleep 2

# Stop nodes
log_info "Stopping nodes..."
kill -TERM $SCHEDULER_PID 2>/dev/null || true
kill -TERM $VICON_PID 2>/dev/null || true
sleep 2

# ============================================================================
# POST-EXPERIMENT SUMMARY
# ============================================================================

log_info ""
log_info "=== Experiment Summary ==="

# Find and report generated log files
SCHEDULER_LOG=$(find "$BACS_LOG_DIR" -name "*${SESSION_ID}_${POLICY}*" -type f -newermt "-5 minutes")
VICON_LOG=$(find "$VICON_LOG_DIR" -name "*${SESSION_ID}_${ROBOT_NAME}*" -type f -newermt "-5 minutes")
ROSBAG_LOG=$(find "$ROSBAG_DIR" -name "*${SESSION_ID}_${POLICY}*" -type d -newermt "-5 minutes")

if [ -n "$SCHEDULER_LOG" ]; then
    log_success "Scheduler Log:"
    for f in $SCHEDULER_LOG; do
        echo "  $f"
        wc -l "$f" | awk '{print "  Lines: " $1}'
    done
else
    log_warning "No scheduler log found"
fi

if [ -n "$VICON_LOG" ]; then
    log_success "Vicon Log:"
    for f in $VICON_LOG; do
        echo "  $f"
        wc -l "$f" | awk '{print "  Lines: " $1}'
    done
else
    log_warning "No Vicon log found"
fi

if [ -n "$ROSBAG_LOG" ]; then
    log_success "ROS 2 Bag:"
    for f in $ROSBAG_LOG; do
        echo "  $f"
        du -sh "$f" | awk '{print "  Size: " $1}'
    done
else
    log_warning "No ROS 2 bag found"
fi

log_success ""
log_success "=== Experiment Completed Successfully ==="
log_success "All logs saved to:"
log_success "  Scheduler: $BACS_LOG_DIR"
log_success "  Vicon: $VICON_LOG_DIR"
log_success "  Bags: $ROSBAG_DIR"
log_success ""
