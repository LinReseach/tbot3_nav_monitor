# TurtleBot3 Navigation Performance Monitor

A ROS 2 Humble package that continuously monitors TurtleBot3 navigation performance and adapts its behaviour in real-time. Built for Gazebo simulation with Docker-based cross-platform deployment on Windows and Mac.

---


![demo](demo/demo.gif)
![demo](demo/demo.gif)
*Full 5-minute demo: https://drive.google.com/file/d/12-QMf5718GcYmyko6j2Z_BnTYTpHJieW/view?usp=sharing


---

## What it does

- Subscribes to Nav2 `NavigateToPose` action feedback and status topics
- Computes 5 navigation performance metrics per completed goal:
  - **Path execution time** — goal assignment to completion
  - **Navigation accuracy** — final distance remaining at goal
  - **Obstacle avoidance efficiency** — actual path length vs straight-line distance
  - **Recovery behavior frequency** — how often the robot gets stuck
  - **Battery consumption** — fictional metric based on distance travelled
- Publishes metrics as JSON on `/tbot3_nav_monitor/metrics`
- Logs one CSV row per goal to `data/navigation_metrics.csv`
- Publishes alert level (OK / WARN / ERROR) via `diagnostic_msgs/DiagnosticArray`


## Architecture

Three nodes with clean separation of concerns:

| Node | Responsibility |
|------|---------------|
| `performance_monitor` | Subscribes to Nav2 action topics, computes metrics, publishes JSON + diagnostics + RViz markers |
| `adaptive_controller` | Consumes metrics, maintains rolling window, calls Nav2 `/set_parameters` when thresholds exceeded |
| `data_logger` | Subscribes to metrics topic, writes one deduplicated CSV row per completed goal |

Shared math and threshold logic lives in `metrics_analyzer.py` (no ROS dependencies — fully unit-testable).

---

## Repository layout

```
tbot3_nav_monitor/
├── Dockerfile                  # Multi-stage build (builder + runtime)
├── docker-compose.yml          # Bind mounts for live editing
├── run_tbot3_humble.ps1        # Windows PowerShell helper (X11 + container start)
├── scripts/
│   └── verify_stack.sh         # Build + test sanity check inside container
├── foxglove/
│   └── README.md               # Foxglove Studio panel setup guide
└── src/tbot3_nav_monitor/
    ├── package.xml
    ├── setup.py
    ├── setup.cfg
    ├── config/
    │   ├── monitor_params.yaml
    │   ├── adaptive_params.yaml
    │   └── logger_params.yaml
    ├── launch/
    │   ├── monitor.launch.py                        # Monitor nodes only
    │   ├── monitor_with_foxglove.launch.py          # Monitor + Foxglove bridge
    │   ├── bringup_sim_nav_monitor.launch.py        # Full stack (wrapper)
    │   └── sim_custom_world_nav_monitor.launch.py   # Gazebo + Nav2 + monitor
    ├── worlds/
    │   ├── basic_obstacles.world
    │   ├── house_like.world
    │   └── narrow_passages.world
    ├── maps/
    │   ├── basic_obstacles.yaml / .pgm
    │   ├── house_like.yaml / .pgm
    │   └── narrow_passages.yaml / .pgm
    └── tbot3_nav_monitor/
        ├── performance_monitor.py
        ├── adaptive_controller.py
        ├── data_logger.py
        └── metrics_analyzer.py
```

---

## Setup

### Prerequisites

| Tool | Windows | Mac |
|------|---------|-----|
| Docker Desktop | [Download](https://www.docker.com/products/docker-desktop/) | [Download](https://www.docker.com/products/docker-desktop/) |
| X11 server | [VcXsrv](https://sourceforge.net/projects/vcxsrv/) | [XQuartz](https://www.xquartz.org/) |
| Foxglove Studio | [Download](https://foxglove.dev/) | [Download](https://foxglove.dev/) |

> **Mac note:** Docker Desktop on Apple Silicon (M1/M2/M3) has known compatibility issues with ROS 2 Humble GUI apps. This project was developed and tested on Windows with Docker Desktop. If using Mac, an older Docker version or Rosetta emulation may be required.

### 1. Clone the repository

```powershell
git clone https://github.com/LinReseach/tbot3_nav_monitor.git
cd tbot3_nav_monitor
```

### 2. Pull the Docker image

```bash
docker pull linlincheng/tbot3_nav_monitor:latest
```

Or build locally:

```powershell
docker build -t tbot3_nav_monitor .
```

### 3. Start VcXsrv (Windows)

- Open **XLaunch**
- Select **Multiple windows**
- Display number: **-1**
- ✅ Check **Disable access control**
- Finish

### 4. Start Foxglove Studio

- Open Foxglove Studio
- Click **Open connection**
- Choose **Foxglove WebSocket**
- URL: `ws://localhost:8765`
- Click **Connect** (do this after launching the monitor with Foxglove bridge)

---

## Quick start (Windows)

```powershell
cd tbot3_nav_monitor

# Allow script execution for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Start the container (handles X11, ports, bind mounts)
.\run_tbot3_humble.ps1
```

Inside the container, build the workspace:

```bash
cd /root/tbot3_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select tbot3_nav_monitor --symlink-install
source install/setup.bash
```

---

## Running the full stack

###  Full simulation (Gazebo + Nav2 + monitor)

```bash
ros2 launch tbot3_nav_monitor sim_custom_world_nav_monitor.launch.py \
  world:=house_like.world \
  map:=house_like.yaml
```

Available worlds and their matching maps:

| World argument | Map argument |
|---------------|-------------|
| `basic_obstacles.world` | `basic_obstacles.yaml` |
| `house_like.world` | `house_like.yaml` |
| `narrow_passages.world` | `narrow_passages.yaml` |

### (new terminal) — Monitor  (attach to existing Nav2 session)

```bash
ros2 launch tbot3_nav_monitor monitor.launch.py
```

### Optional — Monitor + Foxglove bridge

```bash
ros2 launch tbot3_nav_monitor monitor_with_foxglove.launch.py
```

Then connect Foxglove Studio to `ws://localhost:8765` and subscribe to:
- `/tbot3_nav_monitor/metrics` — JSON metrics per goal
- `/tbot3_nav_monitor/diagnostics` — OK / WARN / ERROR alert level
- `/tbot3_nav_monitor/markers` — coloured text marker in 3D panel

---

## Sending Nav2 goals

1. In RViz, click **"2D Pose Estimate"** and click on the map to set the robot's initial position
2. Click **"Nav2 Goal"**, click and drag on the map to set a goal
3. The robot navigates in Gazebo; after completion the monitor logs metrics:

```
[OK]    goal=1d62e885... t=29.2s acc=0.00m rec=0.00/s eff=1.03 bat=0.24
[ERROR] goal=c84ba10c... t=31.8s acc=0.02m rec=0.03/s eff=8.69 bat=0.12
```

Check the CSV output:

```bash
cat ~/tbot3_ws/data/navigation_metrics.csv
```

---

## Building your own maps (optional)

The package ships with pre-built maps. To build a new map with SLAM:

**Terminal 1 — Gazebo only (no Nav2)**
```bash
export TURTLEBOT3_MODEL=burger
ros2 launch gazebo_ros gzserver.launch.py \
  world:=$(ros2 pkg prefix tbot3_nav_monitor)/share/tbot3_nav_monitor/worlds/house_like.world &
ros2 launch gazebo_ros gzclient.launch.py &
ros2 launch turtlebot3_gazebo robot_state_publisher.launch.py &
ros2 run gazebo_ros spawn_entity.py \
  -entity burger \
  -file $(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models/turtlebot3_burger/model.sdf \
  -x -2.0 -y -0.5 -z 0.01
```

**Terminal 2 — SLAM**
```bash
source /opt/ros/humble/setup.bash && source ~/tbot3_ws/install/setup.bash
export TURTLEBOT3_MODEL=burger
ros2 launch turtlebot3_cartographer cartographer.launch.py use_sim_time:=true
```

**Terminal 3 — Teleoperation**
```bash
ros2 run turtlebot3_teleop teleop_keyboard
```

Drive the robot around until the map is complete, then save:

**Terminal 4 — Save map**
```bash
mkdir -p ~/tbot3_ws/src/tbot3_nav_monitor/maps
ros2 run nav2_map_server map_saver_cli -f ~/tbot3_ws/src/tbot3_nav_monitor/maps/house_like
```

---

## Workspace verification

```bash
cp /root/tbot3_ws/scripts/verify_stack.sh /tmp/verify_stack.sh
bash /tmp/verify_stack.sh
```

Expected output:
```
== colcon build tbot3_nav_monitor ==   ✓
== colcon test ==  4 passed in 0.58s   ✓
== ros2 pkg list (sanity) ==           ✓
== OK ==
```

---

## Adaptive behaviour system

The `adaptive_controller` maintains a rolling window of the last 10 goals and adjusts Nav2 parameters when thresholds are exceeded:

| Condition | Threshold | Action |
|-----------|-----------|--------|
| High recovery frequency | `rec > 0.25/s` | Reduce `FollowPath.max_vel_x` → 0.10 m/s |
| Poor navigation accuracy | `acc > 0.5 m` | Increase `general_goal_checker.xy_goal_tolerance` → 0.30 m |
| Inefficient obstacle avoidance | `eff > 1.2` | Increase `inflation_layer.inflation_radius` → 0.6 m; widen `GridBased.tolerance` → 0.3 |

Thresholds and target values are configurable in `config/adaptive_params.yaml`.

---

## Multi-environment testing results

### Summary table

| Metric | basic_obstacles | house_like | narrow_passages |
|--------|----------------|------------|-----------------|
| Unique goals completed | 5 | 10 | 8 |
| Avg execution time (s) | 32.8 | 27.9 | 25.6 |
| Min / Max exec time (s) | 14.3 / 42.7 | 14.4 / 77.5 | 11.6 / 47.9 |
| Avg navigation accuracy (m) | 0.034 | 0.579 | 0.773 |
| Avg obstacle efficiency ratio | 143.1 | 102.6 | 42.8 |
| Goals with recovery behaviors | 2 / 5 | 2 / 10 | 5 / 8 |
| Max recovery frequency (/s) | 0.025 | 0.103 | 0.069 |
| Avg battery consumption (units) | 0.246 | 0.216 | 0.134 |

### Analysis

**basic_obstacles** — Open floor with scattered boxes produced the most consistent execution times (14–43 s) and lowest navigation error (avg 0.034 m). Recovery behaviors were rare (2/5 goals). The high efficiency ratios reflect conservative costmap inflation forcing wide detours even in open space.

**house_like** — Rooms and wall partitions produced the highest variability in execution time (14–78 s). The peak recovery frequency (0.103/s) was the highest across all worlds — partitioned rooms caused the most replanning events. One outlier goal (77.5 s, 5.48 m error) occurred when AMCL localization drifted between rooms, correctly captured and flagged as `[ERROR]` by the monitor.

**narrow_passages** — Tight corridors triggered recovery behaviors in 5 of 8 goals (max 0.069/s). Navigation accuracy was worst on average (0.773 m) due to goals that could not be reached precisely because of passage geometry. The lowest efficiency ratio (avg 42.8) reflects short straight-line distances in a confined space — the ratio is more meaningful here than in open worlds.

**Adaptive controller confirmed active in all worlds:** After sufficient goals accumulated in the rolling window, parameter updates were applied:
- `inflation_layer.inflation_radius`: 0.35 → 0.60 m
- `GridBased.tolerance`: 0.5 → 0.3
- `general_goal_checker.xy_goal_tolerance`: 0.25 → 0.30 m (house_like)

---

## Docker Hub

```bash
docker pull linlincheng/tbot3_nav_monitor:latest
```

Image: https://hub.docker.com/r/linlincheng/tbot3_nav_monitor

---

## Troubleshooting

**Cannot connect Gazebo / black screen**
VcXsrv must be running with "Disable access control" checked before starting the container. The `run_tbot3_humble.ps1` script sets `DISPLAY=host.docker.internal:0.0` automatically.

**Gazebo ignores my world file**
The stock `turtlebot3_gazebo` launch files hardcode specific worlds and do not respect the `world:=` argument. This package uses the generic `gazebo_ros` launch files (`gzserver.launch.py` + `gzclient.launch.py`) instead, which correctly load any world file passed as an argument.

**RViz shows wrong map**
Always pass both `world:=` and `map:=` arguments together — they must match. The `map` argument defaults to `house_like.yaml` so omitting it will always load the house_like map regardless of the Gazebo world.

**`ros2 run tbot3_nav_monitor` — No executable found**
Run `colcon build --packages-select tbot3_nav_monitor --symlink-install` and re-source `install/setup.bash`. The `setup.cfg` file ensures scripts install to `lib/tbot3_nav_monitor/` where `ros2 run` looks.

**Duplicate rows in CSV**
Caused by multiple `data_logger` node instances from previous launches. Kill all monitor processes with `pkill -9 -f "data_logger|performance_monitor|adaptive_controller"` before relaunching.

