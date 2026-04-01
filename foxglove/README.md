# Foxglove Studio

This folder documents how to visualize `tbot3_nav_monitor` topics in [Foxglove Studio](https://foxglove.dev/).

## Prerequisites

- `foxglove_bridge` is installed in the Docker image (`ros-humble-foxglove-bridge`).
- Port **8765** is published to the host (`run_tbot3_humble.ps1` and `docker-compose.yml` map `8765:8765`).

## Launch

With the monitor stack running, start the bridge (or use `monitor_with_foxglove.launch.py`):

```bash
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765 address:=0.0.0.0 use_sim_time:=true
```

Use `use_sim_time:=false` if you are not running Gazebo simulation clock.

## Connect from Windows

1. Open Foxglove Studio on the host.
2. **Open connection** → **Foxglove WebSocket**.
3. URL: `ws://127.0.0.1:8765` (or `ws://localhost:8765`).

## Suggested panels

- **Raw Messages**: subscribe to `/tbot3_nav_monitor/metrics` (JSON in `std_msgs/String`).
- **Diagnostics**: `/tbot3_nav_monitor/diagnostics` (`diagnostic_msgs/DiagnosticArray`).
- **3D** (optional): TF and `/tbot3_nav_monitor/markers` for on-map status markers.

Save your layout in Foxglove (**Layout → Export**) and commit the JSON if you want a reproducible dashboard for graders.
