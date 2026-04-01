# TurtleBot3 Navigation Performance Monitor

A ROS 2 Humble package that continuously monitors TurtleBot3 navigation performance and adapts its behaviour in real-time. Built for Gazebo simulation with Docker-based cross-platform deployment on Windows and Mac.

\---




![demo](demo/demo_gif.gif)

\*Full 5-minute demo: 
https://drive.google.com/file/d/12-QMf5718GcYmyko6j2Z_BnTYTpHJieW/view?usp=sharing


\---

## What it does

* Subscribes to Nav2 `NavigateToPose` action feedback and status topics
* Computes 5 navigation performance metrics per completed goal:

  * **Path execution time** — goal assignment to completion
  * **Navigation accuracy** — final distance remaining at goal
  * **Obstacle avoidance efficiency** — actual path length vs straight-line distance
  * **Recovery behavior frequency** — how often the robot gets stuck
  * **Battery consumption** — fictional metric based on distance travelled
* Publishes metrics as JSON on `/tbot3\_nav\_monitor/metrics`
* Logs one CSV row per goal to `data/navigation\_metrics.csv`
* Publishes alert level (OK / WARN / ERROR) via `diagnostic\_msgs/DiagnosticArray`



## Architecture

Three nodes with clean separation of concerns:

|Node|Responsibility|
|-|-|
|`performance\_monitor`|Subscribes to Nav2 action topics, computes metrics, publishes JSON + diagnostics + RViz markers|
|`adaptive\_controller`|Consumes metrics, maintains rolling window, calls Nav2 `/set\_parameters` when thresholds exceeded|
|`data\_logger`|Subscribes to metrics topic, writes one deduplicated CSV row per completed goal|

Shared math and threshold logic lives in `metrics\_analyzer.py` (no ROS dependencies — fully unit-testable).

\---

## Repository layout

```
tbot3\_nav\_monitor/
├── Dockerfile                  # Multi-stage build (builder + runtime)
├── docker-compose.yml          # Bind mounts for live editing
├── run\_tbot3\_humble.ps1        # Windows PowerShell helper (X11 + container start)
├── scripts/
│   └── verify\_stack.sh         # Build + test sanity check inside container
├── foxglove/
│   └── README.md               # Foxglove Studio panel setup guide
└── src/tbot3\_nav\_monitor/
    ├── package.xml
    ├── setup.py
    ├── setup.cfg
    ├── config/
    │   ├── monitor\_params.yaml
    │   ├── adaptive\_params.yaml
    │   └── logger\_params.yaml
    ├── launch/
    │   ├── monitor.launch.py                        # Monitor nodes only
    │   ├── monitor\_with\_foxglove.launch.py          # Monitor + Foxglove bridge
    │   ├── bringup\_sim\_nav\_monitor.launch.py        # Full stack (wrapper)
    │   └── sim\_custom\_world\_nav\_monitor.launch.py   # Gazebo + Nav2 + monitor
    ├── worlds/
    │   ├── basic\_obstacles.world
    │   ├── house\_like.world
    │   └── narrow\_passages.world
    ├── maps/
    │   ├── basic\_obstacles.yaml / .pgm
    │   ├── house\_like.yaml / .pgm
    │   └── narrow\_passages.yaml / .pgm
    └── tbot3\_nav\_monitor/
        ├── performance\_monitor.py
        ├── adaptive\_controller.py
        ├── data\_logger.py
        └── metrics\_analyzer.py
```

\---

## Setup

### Prerequisites

|Tool|Windows|Mac|
|-|-|-|
|Docker Desktop|[Download](https://www.docker.com/products/docker-desktop/)|[Download](https://www.docker.com/products/docker-desktop/)|
|X11 server|[VcXsrv](https://sourceforge.net/projects/vcxsrv/)|[XQuartz](https://www.xquartz.org/)|
|Foxglove Studio|[Download](https://foxglove.dev/)|[Download](https://foxglove.dev/)|

> \*\*Mac note:\*\* Docker Desktop on Apple Silicon (M1/M2/M3) has known compatibility issues with ROS 2 Humble GUI apps. This project was developed and tested on Windows with Docker Desktop. If using Mac, an older Docker version or Rosetta emulation may be required.

### 1\. Clone the repository

```powershell
git clone https://github.com/LinReseach/tbot3\_nav\_monitor.git
cd tbot3\_nav\_monitor
```

### 2\. Pull the Docker image

```bash
docker pull linlincheng/tbot3\_nav\_monitor:latest
```

Or build locally:

```powershell
docker build -t tbot3\_nav\_monitor .
```

### 3\. Start VcXsrv (Windows)

* Open **XLaunch**
* Select **Multiple windows**
* Display number: **-1**
* ✅ Check **Disable access control**
* Finish

### 4\. Start Foxglove Studio

* Open Foxglove Studio
* Click **Open connection**
* Choose **Foxglove WebSocket**
* URL: `ws://localhost:8765`
* Click **Connect** (do this after launching the monitor with Foxglove bridge)

\---

## Quick start (Windows)

```powershell
cd tbot3\_nav\_monitor

# Allow script execution for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Start the container (handles X11, ports, bind mounts)
.\\run\_tbot3\_humble.ps1
```

Inside the container, build the workspace:

```bash
cd /root/tbot3\_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select tbot3\_nav\_monitor --symlink-install
source install/setup.bash
```

\---

## Running the full stack

### Full simulation (Gazebo + Nav2 + monitor)

```bash
ros2 launch tbot3\_nav\_monitor sim\_custom\_world\_nav\_monitor.launch.py \\
  world:=house\_like.world \\
  map:=house\_like.yaml
```

Available worlds and their matching maps:

|World argument|Map argument|
|-|-|
|`basic\_obstacles.world`|`basic\_obstacles.yaml`|
|`house\_like.world`|`house\_like.yaml`|
|`narrow\_passages.world`|`narrow\_passages.yaml`|

### (new terminal) — Monitor  (attach to existing Nav2 session)

```bash
ros2 launch tbot3\_nav\_monitor monitor.launch.py
```

### Optional — Monitor + Foxglove bridge

```bash
ros2 launch tbot3\_nav\_monitor monitor\_with\_foxglove.launch.py
```

Then connect Foxglove Studio to `ws://localhost:8765` and subscribe to:

* `/tbot3\_nav\_monitor/metrics` — JSON metrics per goal
* `/tbot3\_nav\_monitor/diagnostics` — OK / WARN / ERROR alert level
* `/tbot3\_nav\_monitor/markers` — coloured text marker in 3D panel

\---

## Sending Nav2 goals

1. In RViz, click **"2D Pose Estimate"** and click on the map to set the robot's initial position
2. Click **"Nav2 Goal"**, click and drag on the map to set a goal
3. The robot navigates in Gazebo; after completion the monitor logs metrics:

```
\[OK]    goal=1d62e885... t=29.2s acc=0.00m rec=0.00/s eff=1.03 bat=0.24
\[ERROR] goal=c84ba10c... t=31.8s acc=0.02m rec=0.03/s eff=8.69 bat=0.12
```

Check the CSV output:

```bash
cat \~/tbot3\_ws/data/navigation\_metrics.csv
```

\---

## Building your own maps (optional)

The package ships with pre-built maps. To build a new map with SLAM:

**Terminal 1 — Gazebo only (no Nav2)**

```bash
export TURTLEBOT3\_MODEL=burger
ros2 launch gazebo\_ros gzserver.launch.py \\
  world:=$(ros2 pkg prefix tbot3\_nav\_monitor)/share/tbot3\_nav\_monitor/worlds/house\_like.world \&
ros2 launch gazebo\_ros gzclient.launch.py \&
ros2 launch turtlebot3\_gazebo robot\_state\_publisher.launch.py \&
ros2 run gazebo\_ros spawn\_entity.py \\
  -entity burger \\
  -file $(ros2 pkg prefix turtlebot3\_gazebo)/share/turtlebot3\_gazebo/models/turtlebot3\_burger/model.sdf \\
  -x -2.0 -y -0.5 -z 0.01
```

**Terminal 2 — SLAM**

```bash
source /opt/ros/humble/setup.bash \&\& source \~/tbot3\_ws/install/setup.bash
export TURTLEBOT3\_MODEL=burger
ros2 launch turtlebot3\_cartographer cartographer.launch.py use\_sim\_time:=true
```

**Terminal 3 — Teleoperation**

```bash
ros2 run turtlebot3\_teleop teleop\_keyboard
```

Drive the robot around until the map is complete, then save:

**Terminal 4 — Save map**

```bash
mkdir -p \~/tbot3\_ws/src/tbot3\_nav\_monitor/maps
ros2 run nav2\_map\_server map\_saver\_cli -f \~/tbot3\_ws/src/tbot3\_nav\_monitor/maps/house\_like
```

\---

## Workspace verification

```bash
cp /root/tbot3\_ws/scripts/verify\_stack.sh /tmp/verify\_stack.sh
bash /tmp/verify\_stack.sh
```

Expected output:

```
== colcon build tbot3\_nav\_monitor ==   ✓
== colcon test ==  4 passed in 0.58s   ✓
== ros2 pkg list (sanity) ==           ✓
== OK ==
```

\---

## Adaptive behaviour system

The `adaptive\_controller` maintains a rolling window of the last 10 goals and adjusts Nav2 parameters when thresholds are exceeded:

|Condition|Threshold|Action|
|-|-|-|
|High recovery frequency|`rec > 0.25/s`|Reduce `FollowPath.max\_vel\_x` → 0.10 m/s|
|Poor navigation accuracy|`acc > 0.5 m`|Increase `general\_goal\_checker.xy\_goal\_tolerance` → 0.30 m|
|Inefficient obstacle avoidance|`eff > 1.2`|Increase `inflation\_layer.inflation\_radius` → 0.6 m; widen `GridBased.tolerance` → 0.3|

Thresholds and target values are configurable in `config/adaptive\_params.yaml`.

\---

## Multi-environment testing results

### Summary table

|Metric|basic\_obstacles|house\_like|narrow\_passages|
|-|-|-|-|
|Unique goals completed|5|10|8|
|Avg execution time (s)|32.8|27.9|25.6|
|Min / Max exec time (s)|14.3 / 42.7|14.4 / 77.5|11.6 / 47.9|
|Avg navigation accuracy (m)|0.034|0.579|0.773|
|Avg obstacle efficiency ratio|143.1|102.6|42.8|
|Goals with recovery behaviors|2 / 5|2 / 10|5 / 8|
|Max recovery frequency (/s)|0.025|0.103|0.069|
|Avg battery consumption (units)|0.246|0.216|0.134|

### Analysis

**basic\_obstacles** — Open floor with scattered boxes produced the most consistent execution times (14–43 s) and lowest navigation error (avg 0.034 m). Recovery behaviors were rare (2/5 goals). The high efficiency ratios reflect conservative costmap inflation forcing wide detours even in open space.

**house\_like** — Rooms and wall partitions produced the highest variability in execution time (14–78 s). The peak recovery frequency (0.103/s) was the highest across all worlds — partitioned rooms caused the most replanning events. One outlier goal (77.5 s, 5.48 m error) occurred when AMCL localization drifted between rooms, correctly captured and flagged as `\[ERROR]` by the monitor.

**narrow\_passages** — Tight corridors triggered recovery behaviors in 5 of 8 goals (max 0.069/s). Navigation accuracy was worst on average (0.773 m) due to goals that could not be reached precisely because of passage geometry. The lowest efficiency ratio (avg 42.8) reflects short straight-line distances in a confined space — the ratio is more meaningful here than in open worlds.

**Adaptive controller confirmed active in all worlds:** After sufficient goals accumulated in the rolling window, parameter updates were applied:

* `inflation\_layer.inflation\_radius`: 0.35 → 0.60 m
* `GridBased.tolerance`: 0.5 → 0.3
* `general\_goal\_checker.xy\_goal\_tolerance`: 0.25 → 0.30 m (house\_like)

\---

## Docker Hub

```bash
docker pull linlincheng/tbot3\_nav\_monitor:latest
```

Image: https://hub.docker.com/r/linlincheng/tbot3\_nav\_monitor

\---

## Troubleshooting

**Cannot connect Gazebo / black screen**
VcXsrv must be running with "Disable access control" checked before starting the container. The `run\_tbot3\_humble.ps1` script sets `DISPLAY=host.docker.internal:0.0` automatically.

**Gazebo ignores my world file**
The stock `turtlebot3\_gazebo` launch files hardcode specific worlds and do not respect the `world:=` argument. This package uses the generic `gazebo\_ros` launch files (`gzserver.launch.py` + `gzclient.launch.py`) instead, which correctly load any world file passed as an argument.

**RViz shows wrong map**
Always pass both `world:=` and `map:=` arguments together — they must match. The `map` argument defaults to `house\_like.yaml` so omitting it will always load the house\_like map regardless of the Gazebo world.

**`ros2 run tbot3\_nav\_monitor` — No executable found**
Run `colcon build --packages-select tbot3\_nav\_monitor --symlink-install` and re-source `install/setup.bash`. The `setup.cfg` file ensures scripts install to `lib/tbot3\_nav\_monitor/` where `ros2 run` looks.

**Duplicate rows in CSV**
Caused by multiple `data\_logger` node instances from previous launches. Kill all monitor processes with `pkill -9 -f "data\_logger|performance\_monitor|adaptive\_controller"` before relaunching.

