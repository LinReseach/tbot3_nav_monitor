#!/usr/bin/env bash
# Run inside the container from /root/tbot3_ws after bind-mounting ./src.
set -eo pipefail

cd /root/tbot3_ws
source /opt/ros/humble/setup.bash
if [[ ! -f install/setup.bash ]]; then
  echo "No install/setup.bash — run colcon build first or use the prebuilt image."
  exit 1
fi
source install/setup.bash

echo "== colcon build tbot3_nav_monitor =="
colcon build --packages-select tbot3_nav_monitor --symlink-install
source install/setup.bash

echo "== colcon test =="
colcon test --packages-select tbot3_nav_monitor --event-handlers console_direct+

echo "== ros2 pkg list (sanity) =="
ros2 pkg list | grep -E '^tbot3_nav_monitor$' || {
  echo "Package tbot3_nav_monitor not found in workspace."
  exit 1
}

echo "== OK =="
