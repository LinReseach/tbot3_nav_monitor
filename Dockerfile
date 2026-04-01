#
# Multi-stage build:
#  - builder: build/install the workspace
#  - runtime: install only required runtime ROS deps + copy built artifacts
#
FROM osrf/ros:humble-desktop-full AS builder

RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-colcon-common-extensions \
    python3-rosdep \
    && rm -rf /var/lib/apt/lists/*

# Python deps used by this package (logging/optional plotting).
RUN pip3 install --no-cache-dir pandas matplotlib numpy pyyaml

WORKDIR /root/tbot3_ws
COPY src ./src

# Build the workspace
RUN . /opt/ros/humble/setup.sh && \
    colcon build

FROM osrf/ros:humble-desktop-full AS runtime

RUN apt-get update && apt-get install -y \
    ros-humble-navigation2 \
    ros-humble-nav2-bringup \
    ros-humble-turtlebot3* \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-dynamixel-sdk \
    ros-humble-foxglove-bridge \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir pandas matplotlib numpy pyyaml

ENV TURTLEBOT3_MODEL=burger
ENV GAZEBO_MODEL_PATH=/opt/ros/humble/share/turtlebot3_gazebo/models

WORKDIR /root/tbot3_ws
COPY --from=builder /root/tbot3_ws/install /root/tbot3_ws/install

# `launch_ros` expects Python console-script wrappers to exist under:
#   install/<pkg>/lib/<pkg>/
# Some setuptools/colcon combinations install only under `bin/`.
# Copy shims into the expected location for reliable `ros2 run` / `ros2 launch`.
RUN mkdir -p /root/tbot3_ws/install/tbot3_nav_monitor/lib/tbot3_nav_monitor \
    && (cp -f /root/tbot3_ws/install/tbot3_nav_monitor/bin/* /root/tbot3_ws/install/tbot3_nav_monitor/lib/tbot3_nav_monitor/ 2>/dev/null || true) \
    && chmod +x /root/tbot3_ws/install/tbot3_nav_monitor/lib/tbot3_nav_monitor/* 2>/dev/null || true

# Source ROS and workspace
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
    echo "source /root/tbot3_ws/install/setup.bash" >> ~/.bashrc && \
    echo "export TURTLEBOT3_MODEL=burger" >> ~/.bashrc

CMD ["/bin/bash"]