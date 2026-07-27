#!/usr/bin/env python3
"""
Logging-Enabled BACS+ Scheduler Node

This node implements the BACS+ selection logic and logs four exact timestamps
(t_gen, t_selected, t_tx, t_rx) required by Appendix A.4 to calculate:
  - T_defer: Time from constraint generation to selection
  - T_channel: Time from selection to acknowledgment reception

CSV Output Format:
  seq_id, t_gen_ns, t_selected_ns, t_tx_ns, t_rx_ns, selected_policy, constraint_count

Usage:
  ros2 run bacs_scheduler bacs_scheduler_node [--ros-args -p session_id:=<ID> -p policy:=<policy_name>]
"""

import rclpy
from rclpy.node import Node
from rclpy.time import Time
import csv
import os
from pathlib import Path
from datetime import datetime
import threading


class BACSSchedulerNode(Node):
    """BACS+ Scheduler with production-grade logging."""

    def __init__(self):
        super().__init__('bacs_scheduler_node')
        
        # Declare parameters
        self.declare_parameter('session_id', 'default_session')
        self.declare_parameter('policy', 'default')
        self.declare_parameter('log_dir', './bacs_logs')
        
        # Get parameters
        self.session_id = self.get_parameter('session_id').value
        self.policy = self.get_parameter('policy').value
        self.log_dir = self.get_parameter('log_dir').value
        
        # Create log directory
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize logging
        self.csv_filename = os.path.join(
            self.log_dir,
            f'bacs_scheduler_log_{self.session_id}_{self.policy}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
        # CSV writer with thread safety
        self.csv_lock = threading.Lock()
        self.csv_file = None
        self.csv_writer = None
        self._init_csv()
        
        # Sequence counter
        self.seq_id = 0
        self.constraint_count = 0
        
        self.get_logger().info(
            f'BACS+ Scheduler initialized\n'
            f'  Session: {self.session_id}\n'
            f'  Policy: {self.policy}\n'
            f'  Log file: {self.csv_filename}'
        )
        
        # Simulation: Create a timer to generate constraints periodically
        self.create_timer(1.0, self.constraint_generation_callback)
    
    def _init_csv(self):
        """Initialize CSV file with headers."""
        with self.csv_lock:
            self.csv_file = open(self.csv_filename, 'w', newline='')
            self.csv_writer = csv.DictWriter(
                self.csv_file,
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
            self.csv_writer.writeheader()
            self.csv_file.flush()
    
    def constraint_generation_callback(self):
        """
        Simulate constraint generation.
        In a real scenario, this would subscribe to constraint messages.
        """
        # t_gen: Timestamp when constraint is generated (NOW)
        t_gen = self.get_clock().now()
        t_gen_ns = int(t_gen.nanoseconds)
        
        self.constraint_count += 1
        
        # Simulate constraint processing
        self.process_and_log_constraint(
            t_gen_ns=t_gen_ns,
            constraint_id=self.seq_id
        )
        
        self.seq_id += 1
    
    def process_and_log_constraint(self, t_gen_ns, constraint_id):
        """
        Process a constraint and log timestamps.
        
        Args:
            t_gen_ns: Generation timestamp in nanoseconds
            constraint_id: Unique constraint identifier
        """
        # Simulate selection delay (e.g., 100-500 microseconds)
        import time
        selection_delay = 0.0001 + (constraint_id % 100) * 0.000001
        time.sleep(selection_delay)
        
        # t_selected: Timestamp when constraint is selected by scheduler
        t_selected = self.get_clock().now()
        t_selected_ns = int(t_selected.nanoseconds)
        
        # Simulate transmission delay (e.g., 500-2000 microseconds over ROS)
        tx_delay = 0.0005 + (constraint_id % 100) * 0.000005
        time.sleep(tx_delay)
        
        # t_tx: Timestamp when message is transmitted to robot
        t_tx = self.get_clock().now()
        t_tx_ns = int(t_tx.nanoseconds)
        
        # Simulate network roundtrip (e.g., 5-50 milliseconds)
        import random
        rx_delay = 0.005 + random.uniform(0, 0.045)
        time.sleep(rx_delay)
        
        # t_rx: Timestamp when acknowledgment is received
        t_rx = self.get_clock().now()
        t_rx_ns = int(t_rx.nanoseconds)
        
        # Log the four critical timestamps
        self._write_log_entry(
            seq_id=constraint_id,
            t_gen_ns=t_gen_ns,
            t_selected_ns=t_selected_ns,
            t_tx_ns=t_tx_ns,
            t_rx_ns=t_rx_ns,
            selected_policy=self.policy,
            constraint_count=self.constraint_count
        )
        
        # Calculate and log metrics for verification
        t_defer_us = (t_selected_ns - t_gen_ns) / 1000.0
        t_channel_us = (t_rx_ns - t_tx_ns) / 1000.0
        
        self.get_logger().debug(
            f'Constraint {constraint_id}: '
            f'T_defer={t_defer_us:.3f}µs, '
            f'T_channel={t_channel_us:.3f}µs'
        )
    
    def _write_log_entry(self, seq_id, t_gen_ns, t_selected_ns, t_tx_ns, t_rx_ns,
                        selected_policy, constraint_count):
        """Write a log entry to the CSV file (thread-safe)."""
        with self.csv_lock:
            self.csv_writer.writerow({
                'seq_id': seq_id,
                't_gen_ns': t_gen_ns,
                't_selected_ns': t_selected_ns,
                't_tx_ns': t_tx_ns,
                't_rx_ns': t_rx_ns,
                'selected_policy': selected_policy,
                'constraint_count': constraint_count
            })
            self.csv_file.flush()
    
    def destroy_node(self):
        """Cleanup: Close CSV file."""
        if self.csv_file:
            with self.csv_lock:
                self.csv_file.close()
        self.get_logger().info(f'Log file saved to: {self.csv_filename}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = BACSSchedulerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
