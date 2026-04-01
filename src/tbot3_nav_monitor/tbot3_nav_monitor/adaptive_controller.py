from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

from rcl_interfaces.srv import SetParameters
from rclpy.node import Node
from rclpy.qos import QoSProfile
from rclpy.parameter import Parameter
from std_msgs.msg import String

from .metrics_analyzer import Thresholds


@dataclass(frozen=True)
class _MetricView:
    recovery_frequency_per_sec: float
    navigation_accuracy_m: float
    obstacle_avoidance_efficiency_ratio: float


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


class AdaptiveController(Node):
    """
    Applies adaptive parameter updates to Nav2 nodes based on collected metrics.
    """

    def __init__(self) -> None:
        super().__init__("tbot3_nav_monitor_adaptive_controller")

        # Inputs
        self.declare_parameter("metrics_topic", "/tbot3_nav_monitor/metrics")
        self.declare_parameter("rolling_window_size", 10)
        self.declare_parameter("min_adjust_interval_sec", 2.0)

        # Thresholds (same semantics as metrics_analyzer)
        self.declare_parameter("recovery_frequency_per_sec_high", 0.25)
        self.declare_parameter("navigation_accuracy_m_poor", 0.5)
        self.declare_parameter("obstacle_avoidance_efficiency_low_acceptable", 1.2)

        # Targets (Nav2 node names)
        self.declare_parameter("controller_node_name", "controller_server")
        self.declare_parameter("planner_node_name", "planner_server")
        self.declare_parameter("local_costmap_node_name", "local_costmap/local_costmap")

        # Desired parameter values when thresholds are exceeded.
        # These defaults are conservative and can be overridden in YAML.
        self.declare_parameter("reduced_max_vel_x", 0.2)
        self.declare_parameter("reduced_max_vel_theta", 0.2)

        self.declare_parameter("increased_xy_goal_tolerance", 0.3)
        self.declare_parameter("increased_yaw_goal_tolerance", 0.3)

        self.declare_parameter("conservative_inflation_radius", 0.6)
        self.declare_parameter("conservative_cost_scaling_factor", 10.0)

        self.declare_parameter("conservative_planning_time_sec", 5.0)

        self._metrics_topic = str(self.get_parameter("metrics_topic").value)
        self._window_size = int(self.get_parameter("rolling_window_size").value)
        self._min_adjust_interval_sec = float(self.get_parameter("min_adjust_interval_sec").value)

        self._thresholds = Thresholds(
            recovery_frequency_per_sec_high=float(self.get_parameter("recovery_frequency_per_sec_high").value),
            navigation_accuracy_m_poor=float(self.get_parameter("navigation_accuracy_m_poor").value),
            obstacle_avoidance_efficiency_low_acceptable=float(
                self.get_parameter("obstacle_avoidance_efficiency_low_acceptable").value
            ),
        )

        self._controller_node_name = str(self.get_parameter("controller_node_name").value)
        self._planner_node_name = str(self.get_parameter("planner_node_name").value)
        self._local_costmap_node_name = str(self.get_parameter("local_costmap_node_name").value)

        self._reduced_max_vel_x = float(self.get_parameter("reduced_max_vel_x").value)
        self._reduced_max_vel_theta = float(self.get_parameter("reduced_max_vel_theta").value)

        self._increased_xy_goal_tolerance = float(self.get_parameter("increased_xy_goal_tolerance").value)
        self._increased_yaw_goal_tolerance = float(self.get_parameter("increased_yaw_goal_tolerance").value)

        self._conservative_inflation_radius = float(self.get_parameter("conservative_inflation_radius").value)
        self._conservative_cost_scaling_factor = float(
            self.get_parameter("conservative_cost_scaling_factor").value
        )
        self._conservative_planning_time_sec = float(self.get_parameter("conservative_planning_time_sec").value)

        qos = QoSProfile(depth=10)
        self._sub = self.create_subscription(String, self._metrics_topic, self._on_metrics, qos)

        self._window: Deque[_MetricView] = deque(maxlen=self._window_size)
        self._last_adjustment_ts: float = 0.0

        # Parameter set cache: we avoid reallocating client objects by creating on demand.
        self._service_clients: Dict[str, Any] = {}

        self.get_logger().info(f"Adaptive controller listening on {self._metrics_topic}")

    def _get_set_parameters_client(self, target_node_name: str):
        if target_node_name in self._service_clients:
            return self._service_clients[target_node_name]
        service_name = f"/{target_node_name}/set_parameters"
        client = self.create_client(SetParameters, service_name)
        self._service_clients[target_node_name] = client
        return client

    def _set_nav2_parameters(self, target_node_name: str, params: Dict[str, Any]) -> None:
        """
        Fire-and-forget set_parameters call. Logs result when available.
        """
        client = self._get_set_parameters_client(target_node_name)
        if not client.service_is_ready():
            self.get_logger().warning(f"set_parameters service not ready for {target_node_name}")
            return

        request = SetParameters.Request()
        request.parameters = []
        for name, value in params.items():
            # rclpy.Parameter supports numeric/bool/string types and converts to rcl_interfaces/msg/Parameter.
            request.parameters.append(Parameter(name=name, value=value).to_parameter_msg())

        future = client.call_async(request)

        def _done(fut):
            try:
                result = fut.result()
                ok = all(getattr(r, "successful", False) for r in result.results)
                if ok:
                    self.get_logger().info(f"Updated parameters for {target_node_name}: {list(params.keys())}")
                else:
                    self.get_logger().warning(f"Parameter update had failures for {target_node_name}")
            except Exception as e:
                self.get_logger().warning(f"Parameter update failed for {target_node_name}: {e}")

        future.add_done_callback(_done)

    def _compute_window_view(self) -> Optional[_MetricView]:
        if not self._window:
            return None
        recovery_avg = sum(v.recovery_frequency_per_sec for v in self._window) / len(self._window)
        accuracy_avg = sum(v.navigation_accuracy_m for v in self._window) / len(self._window)
        obstacle_avg = sum(v.obstacle_avoidance_efficiency_ratio for v in self._window) / len(self._window)
        return _MetricView(
            recovery_frequency_per_sec=recovery_avg,
            navigation_accuracy_m=accuracy_avg,
            obstacle_avoidance_efficiency_ratio=obstacle_avg,
        )

    def _on_metrics(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except Exception:
            return

        view = _MetricView(
            recovery_frequency_per_sec=_safe_float(payload.get("recovery_frequency_per_sec"), 0.0),
            navigation_accuracy_m=_safe_float(payload.get("navigation_accuracy_m"), 0.0),
            obstacle_avoidance_efficiency_ratio=_safe_float(
                payload.get("obstacle_avoidance_efficiency_ratio"), 0.0
            ),
        )

        self._window.append(view)
        if len(self._window) < max(3, int(self._window_size * 0.3)):
            return

        now = time.time()
        if now - self._last_adjustment_ts < self._min_adjust_interval_sec:
            return

        window_view = self._compute_window_view()
        if window_view is None:
            return

        desired_updates: Dict[str, Dict[str, Any]] = {}

        # 1) Frequent recovery behaviors -> reduce max velocity.
        if window_view.recovery_frequency_per_sec >= self._thresholds.recovery_frequency_per_sec_high:
            desired_updates[self._controller_node_name] = {
                "FollowPath.max_vel_x": self._reduced_max_vel_x,
                "FollowPath.max_vel_theta": self._reduced_max_vel_theta,
            }

        # 2) Consistently poor navigation accuracy -> increase goal tolerance.
        if window_view.navigation_accuracy_m >= self._thresholds.navigation_accuracy_m_poor:
            desired_updates.setdefault(self._controller_node_name, {}).update({
                "general_goal_checker.xy_goal_tolerance": self._increased_xy_goal_tolerance,
                "general_goal_checker.yaw_goal_tolerance": self._increased_yaw_goal_tolerance,
            })

        # 3) Obstacle avoidance inefficiency -> conservative planning + adjust local costmap.
        if window_view.obstacle_avoidance_efficiency_ratio >= self._thresholds.obstacle_avoidance_efficiency_low_acceptable:
            # Planner conservatism (generic param; override if your nav2 uses different names).
            desired_updates.setdefault(self._planner_node_name, {})[
                "GridBased.tolerance"
            ] = 0.3  # wider tolerance = more conservative planning

            # Costmap inflation conservatism (generic param name; override if needed).
            desired_updates.setdefault(self._local_costmap_node_name, {})[
                "inflation_layer.inflation_radius"
            ] = self._conservative_inflation_radius
            desired_updates.setdefault(self._local_costmap_node_name, {})[
                "inflation_layer.cost_scaling_factor"
            ] = self._conservative_cost_scaling_factor

        if not desired_updates:
            return

        # Apply updates.
        for target_node_name, params in desired_updates.items():
            self._set_nav2_parameters(target_node_name, params)

        self._last_adjustment_ts = now


def main() -> None:
    import rclpy

    rclpy.init()
    node = AdaptiveController()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

