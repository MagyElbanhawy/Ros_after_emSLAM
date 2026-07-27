#!/usr/bin/env python3
"""
Vicon Ground Truth Logger Node

This node subscribes to the Vicon ROS bridge topics and logs high-frequency
ground truth poses. This raw data is used in Python/Matlab to calculate:
  - Map-Alignment RMSE
  - Pose RMSE for Table A2

CSV Output Format:
  timestamp_ns, x, y, z, roll, rad_pitch, rad_yaw, vx, vy, vz

Usage:
  ros2 run bacs_scheduler vicon_logger_node [--ros-args -p session_id:=<ID> -p robot_name:=<robot_name>]
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped, TransformStamped
from nav_msgs.msg import Odometry
from tf2_ros import TransformListener, Buffer
import csv
import os
from pathlib import Path
from datetime import datetime
import threading
import math


class ViconLoggerNode(Node):
    """Vicon ground truth logger for pose tracking."""

    def __init__(self):
        super().__init__('vicon_logger_node')
        
        # Declare parameters
        self.declare_parameter('session_id', 'default_session')
        self.declare_parameter('robot_name', 'robot_0')
        self.declare_parameter('log_dir', './vicon_logs')
        self.declare_parameter('vicon_topic', '/vicon/robot_0/robot_0')
        self.declare_parameter('odom_topic', '/odom')
        
        # Get parameters
        self.session_id = self.get_parameter('session_id').value
        self.robot_name = self.get_parameter('robot_name').value
        self.log_dir = self.get_parameter('log_dir').value
        self.vicon_topic = self.get_parameter('vicon_topic').value
        self.odom_topic = self.get_parameter('odom_topic').value
        
        # Create log directory
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize logging
        self.csv_filename = os.path.join(
            self.log_dir,
            f'vicon_ground_truth_{self.session_id}_{self.robot_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
        
        # CSV writer with thread safety
        self.csv_lock = threading.Lock()
        self.csv_file = None
        self.csv_writer = None
        self._init_csv()
        
        # Pose counter
        self.pose_count = 0
        
        # Subscribe to Vicon pose topic
        self.vicon_subscription = self.create_subscription(
            PoseStamped,
            self.vicon_topic,
            self.vicon_callback,
            qos_profile=rclpy.qos.QoSProfile(
                depth=10,
                reliability=rclpy.qos.ReliabilityPolicy.BEST_EFFORT
            )
        )
        
        # Subscribe to odometry for velocity estimates
        self.odom_subscription = self.create_subscription(
            Odometry,
            self.odom_topic,
            self.odom_callback,
            qos_profile=rclpy.qos.QoSProfile(
                depth=10,
                reliability=rclpy.qos.ReliabilityPolicy.BEST_EFFORT
            )
        )
        
        # Current velocity state (updated by odometry)
        self.current_vx = 0.0
        self.current_vy = 0.0
        self.current_vz = 0.0
        self.velocity_lock = threading.Lock()
        
        self.get_logger().info(
            f'Vicon Logger initialized\n'
            f'  Session: {self.session_id}\n'
            f'  Robot: {self.robot_name}\n'
            f'  Vicon topic: {self.vicon_topic}\n'
            f'  Odometry topic: {self.odom_topic}\n'
            f'  Log file: {self.csv_filename}'
        )
    
    def _init_csv(self):
        """Initialize CSV file with headers."""
        with self.csv_lock:
            self.csv_file = open(self.csv_filename, 'w', newline='')
            self.csv_writer = csv.DictWriter(
                self.csv_file,
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
            self.csv_writer.writeheader()
            self.csv_file.flush()
    
    def quaternion_to_euler(self, qx, qy, qz, qw):
        """
        Convert quaternion to Euler angles (roll, pitch, yaw).
        
        Args:
            qx, qy, qz, qw: Quaternion components
            
        Returns:
            roll, pitch, yaw in radians
        """
        # Roll (rotation around x-axis)
        sinr_cosp = 2 * (qw * qx + qy * qz)
        cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
        roll = math.atan2(sinr_cosp, cosr_cosp)
        
        # Pitch (rotation around y-axis)
        sinp = 2 * (qw * qy - qz * qx)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)
        
        # Yaw (rotation around z-axis)
        siny_cosp = 2 * (qw * qz + qx * qy)
        cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        
        return roll, pitch, yaw
    
    def vicon_callback(self, msg: PoseStamped):
        """
        Callback for Vicon pose messages.
        
        Args:
            msg: PoseStamped message containing pose data
        """
        # Extract timestamp
        timestamp_ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec
        
        # Extract position
        x = msg.pose.position.x
        y = msg.pose.position.y
        z = msg.pose.position.z
        
        # Extract orientation (quaternion)
        qx = msg.pose.orientation.x
        qy = msg.pose.orientation.y
        qz = msg.pose.orientation.z
        qw = msg.pose.orientation.w
        
        # Convert to Euler angles
        roll, pitch, yaw = self.quaternion_to_euler(qx, qy, qz, qw)
        
        # Get current velocity from odometry
        with self.velocity_lock:
            vx, vy, vz = self.current_vx, self.current_vy, self.current_vz
        
        # Log the pose
        self._write_log_entry(
            timestamp_ns=timestamp_ns,
            x=x,
            y=y,
            z=z,
            roll_rad=roll,
            pitch_rad=pitch,
            yaw_rad=yaw,
            vx=vx,
            vy=vy,
            vz=vz
        )
        
        self.pose_count += 1
        if self.pose_count % 100 == 0:
            self.get_logger().debug(f'Logged {self.pose_count} poses')
    
    def odom_callback(self, msg: Odometry):
        """
        Callback for odometry messages (velocity extraction).
        
        Args:
            msg: Odometry message containing velocity data
        """
        with self.velocity_lock:
            self.current_vx = msg.twist.twist.linear.x
            self.current_vy = msg.twist.twist.linear.y
            self.current_vz = msg.twist.twist.linear.z
    
    def _write_log_entry(self, timestamp_ns, x, y, z, roll_rad, pitch_rad, yaw_rad,
                        vx, vy, vz):
        """Write a log entry to the CSV file (thread-safe)."""
        with self.csv_lock:
            self.csv_writer.writerow({
                'timestamp_ns': timestamp_ns,
                'x': f'{x:.6f}',
                'y': f'{y:.6f}',
                'z': f'{z:.6f}',
                'roll_rad': f'{roll_rad:.6f}',
                'pitch_rad': f'{pitch_rad:.6f}',
                'yaw_rad': f'{yaw_rad:.6f}',
                'vx': f'{vx:.6f}',
                'vy': f'{vy:.6f}',
                'vz': f'{vz:.6f}'
            })
            self.csv_file.flush()
    
    def destroy_node(self):
        """Cleanup: Close CSV file."""
        if self.csv_file:
            with self.csv_lock:
                self.csv_file.close()
        self.get_logger().info(f'Log file saved to: {self.csv_filename}')
        self.get_logger().info(f'Total poses logged: {self.pose_count}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ViconLoggerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
