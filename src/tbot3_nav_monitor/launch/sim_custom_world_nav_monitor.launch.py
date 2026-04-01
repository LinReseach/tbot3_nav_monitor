#!/usr/bin/env python3
"""Custom .world from tbot3_nav_monitor + TurtleBot3 spawn + Nav2 + monitor.

The map is loaded from share/tbot3_nav_monitor/maps/ and defaults to the
map whose stem matches the world name (e.g. house_like.world → house_like.yaml).
Override with map:=<filename>.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description() -> LaunchDescription:
    pkg_gazebo_ros = get_package_share_directory("gazebo_ros")
    launch_file_dir = os.path.join(
        get_package_share_directory("turtlebot3_gazebo"), "launch"
    )
    tb3_nav2 = get_package_share_directory("turtlebot3_navigation2")
    pkg = get_package_share_directory("tbot3_nav_monitor")

    # Nav2 params file (keep using the stock TurtleBot3 params — only the map changes)
    model = os.environ.get("TURTLEBOT3_MODEL", "burger")
    distro = os.environ.get("ROS_DISTRO", "humble")
    if distro == "humble":
        default_params = os.path.join(tb3_nav2, "param", distro, f"{model}.yaml")
    else:
        default_params = os.path.join(tb3_nav2, "param", f"{model}.yaml")

    use_sim_time = LaunchConfiguration("use_sim_time")
    x_pose     = LaunchConfiguration("x_pose")
    y_pose     = LaunchConfiguration("y_pose")
    world_name = LaunchConfiguration("world")
    map_file   = LaunchConfiguration("map")

    world_path = PathJoinSubstitution(
        [FindPackageShare("tbot3_nav_monitor"), "worlds", world_name]
    )
    # Resolved inside share/tbot3_nav_monitor/maps/ — your saved map, not the stock one
    map_path = PathJoinSubstitution(
        [FindPackageShare("tbot3_nav_monitor"), "maps", map_file]
    )

    declare_world = DeclareLaunchArgument(
        "world",
        default_value="basic_obstacles.world",
        description="World file under share/tbot3_nav_monitor/worlds/",
    )
    declare_map = DeclareLaunchArgument(
        "map",
        default_value="house_like.yaml",
        description=(
            "Map YAML filename under share/tbot3_nav_monitor/maps/ "
            "(e.g. house_like.yaml, basic_obstacles.yaml, narrow_passages.yaml)"
        ),
    )
    declare_use_sim_time = DeclareLaunchArgument(
        "use_sim_time", default_value="true", description="Use Gazebo /clock"
    )
    declare_x = DeclareLaunchArgument(
        "x_pose", default_value="-2.0", description="Spawn x (m)"
    )
    declare_y = DeclareLaunchArgument(
        "y_pose", default_value="-0.5", description="Spawn y (m)"
    )

    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, "launch", "gzserver.launch.py")
        ),
        launch_arguments={"world": world_path}.items(),
    )

    gzclient_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, "launch", "gzclient.launch.py")
        )
    )

    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, "robot_state_publisher.launch.py")
        ),
        launch_arguments={"use_sim_time": use_sim_time}.items(),
    )

    spawn_turtlebot_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, "spawn_turtlebot3.launch.py")
        ),
        launch_arguments={"x_pose": x_pose, "y_pose": y_pose}.items(),
    )

    navigation2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_nav2, "launch", "navigation2.launch.py")
        ),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "map": map_path,            # ← your map, not the stock TurtleBot3 one
            "params_file": default_params,
        }.items(),
    )

    monitor = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg, "launch", "monitor.launch.py")
        )
    )

    return LaunchDescription(
        [
            declare_world,
            declare_map,
            declare_use_sim_time,
            declare_x,
            declare_y,
            gzserver_cmd,
            gzclient_cmd,
            robot_state_publisher_cmd,
            spawn_turtlebot_cmd,
            navigation2,
            monitor,
        ]
    )
