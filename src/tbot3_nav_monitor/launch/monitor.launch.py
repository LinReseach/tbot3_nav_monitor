from __future__ import annotations

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess


def generate_launch_description() -> LaunchDescription:
    pkg_share = get_package_share_directory("tbot3_nav_monitor")

    monitor_params = os.path.join(pkg_share, "config", "monitor_params.yaml")
    adaptive_params = os.path.join(pkg_share, "config", "adaptive_params.yaml")
    logger_params = os.path.join(pkg_share, "config", "logger_params.yaml")

    return LaunchDescription(
        [
            # Use `ros2 run` to avoid relying on the `lib/<pkg>` executable layout.
            # (Our Python entrypoints are installed as console scripts under `bin`.)
            ExecuteProcess(
                cmd=[
                    "ros2",
                    "run",
                    "tbot3_nav_monitor",
                    "performance_monitor",
                    "--ros-args",
                    "--params-file",
                    monitor_params,
                ],
                output="screen",
            ),
            ExecuteProcess(
                cmd=[
                    "ros2",
                    "run",
                    "tbot3_nav_monitor",
                    "adaptive_controller",
                    "--ros-args",
                    "--params-file",
                    adaptive_params,
                ],
                output="screen",
            ),
            ExecuteProcess(
                cmd=[
                    "ros2",
                    "run",
                    "tbot3_nav_monitor",
                    "data_logger",
                    "--ros-args",
                    "--params-file",
                    logger_params,
                ],
                output="screen",
            ),
        ]
    )
