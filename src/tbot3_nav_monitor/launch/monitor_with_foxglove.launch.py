#!/usr/bin/env python3
"""Performance monitor nodes plus Foxglove WebSocket bridge for Studio visualization."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description() -> LaunchDescription:
    pkg = get_package_share_directory("tbot3_nav_monitor")

    monitor = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg, "launch", "monitor.launch.py")
        )
    )

    # Exposes ROS graph to Foxglove Studio at ws://<host>:8765
    foxglove = ExecuteProcess(
        cmd=[
            "ros2",
            "launch",
            "foxglove_bridge",
            "foxglove_bridge_launch.xml",
            "port:=8765",
            "address:=0.0.0.0",
            "use_sim_time:=true",
        ],
        output="screen",
    )

    return LaunchDescription([monitor, foxglove])
