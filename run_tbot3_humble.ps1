# ============================================================
# TurtleBot3 ROS 2 Humble - Docker Launch Script (Windows)
# Mirrors the working Noetic X11 + Gazebo configuration
# - First run: starts the container
# - Subsequent runs: opens a new terminal inside it
# ============================================================

# Create required local directories if they don't exist
$dirs = @("maps", "data", "src", "worlds")
foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Host "Created directory: $dir"
    }
}

# ============================================================
# X Server check - make sure VcXsrv or Xming is running
# ============================================================
$xservers = @("vcxsrv", "xming")
$xRunning = $false
foreach ($x in $xservers) {
    if (Get-Process -Name $x -ErrorAction SilentlyContinue) {
        Write-Host "X server detected: $x" -ForegroundColor Green
        $xRunning = $true
        break
    }
}
if (-not $xRunning) {
    Write-Warning "No X server (VcXsrv or Xming) detected. Gazebo GUI will not work."
    Write-Warning "Launch VcXsrv with 'Disable access control' checked, then re-run this script."
    $response = Read-Host "Continue anyway? (y/n)"
    if ($response -ne "y") { exit 1 }
}

# ============================================================
# Run or attach to the Humble container
# ============================================================
$containerName = "tbot3_humble"
$running = docker ps --filter "name=^/${containerName}$" --format "{{.Names}}"

if ($running -eq $containerName) {
    Write-Host "`nContainer '$containerName' is already running - opening new terminal inside it..." -ForegroundColor Yellow
    docker exec -it $containerName bash
} else {
    Write-Host "`nStarting TurtleBot3 ROS 2 Humble container..." -ForegroundColor Cyan
    docker run -it --rm `
        --privileged `
        --name $containerName `
        -e DISPLAY=host.docker.internal:0 `
        -e LIBGL_ALWAYS_SOFTWARE=1 `
        -e QT_X11_NO_MITSHM=1 `
        -e GAZEBO_GUI_USE_BUILTIN_CAMERA=0 `
        -e MESA_GL_VERSION_OVERRIDE=3.3 `
        -e MESA_GLSL_VERSION_OVERRIDE=330 `
        -e TURTLEBOT3_MODEL=burger `
        -e ROS_DOMAIN_ID=30 `
        -e GAZEBO_RESOURCE_PATH=/root/tbot3_ws/worlds:/usr/share/gazebo-11 `
        -e GAZEBO_MODEL_PATH=/root/tbot3_ws/models:/opt/ros/humble/share/turtlebot3_gazebo/models `
        -v "${PWD}/maps:/root/tbot3_ws/maps:rw" `
        -v "${PWD}/data:/root/tbot3_ws/data:rw" `
        -v "${PWD}/src:/root/tbot3_ws/src:rw" `
        -v "${PWD}/scripts:/root/tbot3_ws/scripts:ro" `
        -v "${PWD}/src/tbot3_nav_monitor/worlds:/root/tbot3_ws/worlds:rw" `
        -p "8765:8765" `
        -v /tmp/.X11-unix:/tmp/.X11-unix:rw `
        tbot3_nav_monitor `
        bash
}
