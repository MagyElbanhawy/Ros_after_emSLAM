"""Launch the BACS scheduler node with parameters from config/bacs.yaml."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory("bacs_scheduler"), "config", "bacs.yaml")
    return LaunchDescription([
        Node(
            package="bacs_scheduler",
            executable="bacs_scheduler_node.py",
            name="bacs_scheduler",
            output="screen",
            parameters=[config],
            remappings=[
                ("local_constraint_candidates", "/slam/constraint_candidates"),
                ("selected_constraints", "/lora/tx_constraints"),
                ("radio_stats", "/lora/stats"),
            ],
        ),
    ])
