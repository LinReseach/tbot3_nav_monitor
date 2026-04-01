#!/usr/bin/env python3
"""Full sim + Nav2 + monitor using worlds from this package (default: basic_obstacles.world).

Previously this file included turtlebot3_gazebo/turtlebot3_world.launch.py, which always loads
the stock TurtleBot3 world. It now delegates to sim_custom_world_nav_monitor.launch.py so you
get the worlds under share/tbot3_nav_monitor/worlds/ (override with world:=...).
"""

# src/tbot3_nav_monitor/launch/bringup_sim_nav_monitor.launch.py

#!/usr/bin/env python3
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

def generate_launch_description() -> LaunchDescription:
    pkg = get_package_share_directory("tbot3_nav_monitor")

    # ✅ Declare world arg HERE so it's visible on the command line
    declare_world = DeclareLaunchArgument(
        "world",
        default_value="basic_obstacles.world",
        description="World file under share/tbot3_nav_monitor/worlds/",
    )

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg, "launch", "sim_custom_world_nav_monitor.launch.py")
        ),
        # ✅ Forward the world argument into the child launch file
        launch_arguments={"world": LaunchConfiguration("world")}.items(),
    )

    return LaunchDescription([declare_world, sim])
