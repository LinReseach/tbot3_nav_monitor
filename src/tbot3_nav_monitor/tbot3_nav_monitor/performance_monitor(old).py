from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from rclpy.node import Node

from action_msgs.msg import GoalStatusArray
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus
from geometry_msgs.msg import Point
from rclpy.qos import QoSProfile
from std_msgs.msg import String
from tf2_ros import TransformException
from visualization_msgs.msg import Marker, MarkerArray

from nav2_msgs.action._navigate_to_pose import NavigateToPose_FeedbackMessage

from .metrics_analyzer import (
    MetricsSample,
    Thresholds,
    assess_degradation,
    choose_overall_alert_level,
    compute_battery_consumption_units,
    compute_obstacle_avoidance_efficiency_ratio,
    compute_recovery_frequency_per_sec,
)


def _uuid_to_str(uuid_msg: Any) -> str:
    """
    unique_identifier_msgs/UUID -> hex string.
    """
    try:
        if hasattr(uuid_msg, "uuid"):
            return "".join(f"{int(b):02x}" for b in uuid_msg.uuid)
    except Exception:
        pass
    return str(uuid_msg)


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


@dataclass
class _SessionState:
    goal_id: str
    start_time_ros: float
    # First observed distance_remaining (used as straight-line "optimal" length proxy)
    optimal_path_len_m: Optional[float] = None
    # Last observed distance_remaining
    last_distance_remaining_m: Optional[float] = None
    # Recoveries count from feedback
    recoveries_count: int = 0
    # Approximate path length from successive feedback current_pose updates
    actual_path_len_m: float = 0.0
    last_feedback_xy: Optional[tuple[float, float]] = None

    finalized: bool = False
    end_time_ros: Optional[float] = None


class PerformanceMonitor(Node):
    """
    Monitors Nav2 NavigateToPose metrics and publishes them continuously.
    """

    def __init__(self) -> None:
        super().__init__("tbot3_nav_monitor_performance_monitor")

        self.declare_parameter("navigate_action_name", "navigate_to_pose")
        self.declare_parameter("metrics_topic", "/tbot3_nav_monitor/metrics")
        self.declare_parameter("diagnostics_topic", "/tbot3_nav_monitor/diagnostics")
        self.declare_parameter("markers_topic", "/tbot3_nav_monitor/markers")

        # Fictional battery consumption model.
        self.declare_parameter("battery_units_per_meter", 0.05)

        # Alert thresholds (single-goal evaluation; controller uses rolling averages).
        self.declare_parameter("recovery_frequency_per_sec_high", 0.25)
        self.declare_parameter("navigation_accuracy_m_poor", 0.5)
        self.declare_parameter("obstacle_avoidance_efficiency_low_acceptable", 1.2)

        self._navigate_action_name: str = str(self.get_parameter("navigate_action_name").value)
        self._metrics_topic: str = str(self.get_parameter("metrics_topic").value)
        self._diagnostics_topic: str = str(self.get_parameter("diagnostics_topic").value)
        self._markers_topic: str = str(self.get_parameter("markers_topic").value)
        self._battery_units_per_meter: float = float(self.get_parameter("battery_units_per_meter").value)

        qos = QoSProfile(depth=10)
        self._metrics_pub = self.create_publisher(String, self._metrics_topic, qos)
        self._diag_pub = self.create_publisher(DiagnosticArray, self._diagnostics_topic, qos)
        self._marker_pub = self.create_publisher(MarkerArray, self._markers_topic, qos)

        # Track each goal via its UUID string.
        self._sessions: dict[str, _SessionState] = {}

        # --- Subscriptions to Nav2 NavigateToPose action internals.
        #
        # ROS2 action transport uses these topic conventions:
        #   /<action_name>/_action/status
        #   /<action_name>/_action/feedback
        #   /<action_name>/_action/result
        #
        # These are typically present when Nav2 is running.
        action_base = f"/{self._navigate_action_name}/_action"
        self.create_subscription(
            GoalStatusArray,
            f"{action_base}/status",
            self._on_action_status,
            qos,
        )

        # Import message classes for feedback.
        self.create_subscription(
            NavigateToPose_FeedbackMessage,
            f"{action_base}/feedback",
            self._on_action_feedback,
            qos,
        )

        self.get_logger().info(f"Listening to Nav2 action topics under {action_base}/...")

    def _now_ros_sec(self) -> float:
        # rclpy clocks are monotonic; for timestamps we also include wall time.
        return time.time()

    def _make_thresholds(self) -> Thresholds:
        return Thresholds(
            recovery_frequency_per_sec_high=float(self.get_parameter("recovery_frequency_per_sec_high").value),
            navigation_accuracy_m_poor=float(self.get_parameter("navigation_accuracy_m_poor").value),
            obstacle_avoidance_efficiency_low_acceptable=float(
                self.get_parameter("obstacle_avoidance_efficiency_low_acceptable").value
            ),
        )

    def _extract_session_from_uuid(self, goal_uuid_str: str) -> _SessionState:
        if goal_uuid_str not in self._sessions:
            self._sessions[goal_uuid_str] = _SessionState(goal_id=goal_uuid_str, start_time_ros=self._now_ros_sec())
        return self._sessions[goal_uuid_str]

    def _finalize_session_and_publish(self, session: _SessionState) -> None:
        """
        Computes all metrics from the accumulated feedback snapshot
        and publishes JSON metrics + diagnostics + visualization.
        """
        if session.finalized:
            return

        session.finalized = True
        session.end_time_ros = self._now_ros_sec()

        exec_time = max(0.0, float(session.end_time_ros - session.start_time_ros))
        navigation_accuracy_m = float(session.last_distance_remaining_m or 0.0)
        optimal_len = float(session.optimal_path_len_m or 0.0)
        obstacle_eff = compute_obstacle_avoidance_efficiency_ratio(session.actual_path_len_m, optimal_len)
        recovery_freq = compute_recovery_frequency_per_sec(session.recoveries_count, exec_time)
        battery_units = compute_battery_consumption_units(session.actual_path_len_m, self._battery_units_per_meter)

        sample = MetricsSample(
            timestamp_unix=float(time.time()),
            goal_id=session.goal_id,
            path_execution_time_sec=exec_time,
            navigation_accuracy_m=navigation_accuracy_m,
            obstacle_avoidance_efficiency_ratio=float(obstacle_eff),
            recovery_frequency_per_sec=float(recovery_freq),
            battery_consumption_units=float(battery_units),
        )

        # Publish JSON metrics for CSV logging and visualization.
        self._metrics_pub.publish(String(data=json.dumps(sample.__dict__)))

        # Alerts + diagnostics + visualization.
        thresholds = self._make_thresholds()
        degraded_flags = assess_degradation(sample, thresholds)
        alert_level = choose_overall_alert_level(degraded_flags)

        diag_array = DiagnosticArray()
        diag_array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = "tbot3_nav_monitor"
        status.level = (
            DiagnosticStatus.ERROR
            if alert_level == "ERROR"
            else (DiagnosticStatus.WARN if alert_level == "WARN" else DiagnosticStatus.OK)
        )
        status.message = (
            f"alert={alert_level}, "
            f"time={exec_time:.3f}s, "
            f"accuracy={navigation_accuracy_m:.3f}m, "
            f"recovery_rate={recovery_freq:.3f}/s, "
            f"obstacle_eff={obstacle_eff:.3f}"
        )
        diag_array.status.append(status)
        self._diag_pub.publish(diag_array)

        # Simple RViz text marker near last known feedback position.
        marker_array = MarkerArray()
        m = Marker()
        m.header.frame_id = "map"
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns = "tbot3_nav_monitor"
        m.id = 0
        m.type = Marker.TEXT_VIEW_FACING
        m.action = Marker.ADD
        m.scale.z = 0.2
        m.color.a = 1.0

        if alert_level == "ERROR":
            m.color.r, m.color.g, m.color.b = 1.0, 0.1, 0.1
        elif alert_level == "WARN":
            m.color.r, m.color.g, m.color.b = 1.0, 0.8, 0.1
        else:
            m.color.r, m.color.g, m.color.b = 0.2, 1.0, 0.2

        if session.last_feedback_xy is not None:
            m.pose.position = Point(
                x=float(session.last_feedback_xy[0]),
                y=float(session.last_feedback_xy[1]),
                z=0.2,
            )
        else:
            m.pose.position = Point(x=0.0, y=0.0, z=0.2)
        m.pose.orientation.w = 1.0

        m.text = (
            f"[{alert_level}] "
            f"t={exec_time:.1f}s "
            f"acc={navigation_accuracy_m:.2f}m "
            f"rec={recovery_freq:.2f}/s "
            f"eff={obstacle_eff:.2f}"
        )
        marker_array.markers.append(m)
        self._marker_pub.publish(marker_array)

    def _on_action_status(self, msg: GoalStatusArray) -> None:
        # Create sessions when goals become ACTIVE.
        # GoalStatusArray.goals entries have status and goal_info.goal_id.
        for goal_status in msg.goals:
            try:
                goal_id_uuid = goal_status.goal_info.goal_id
                goal_uuid_str = _uuid_to_str(goal_id_uuid)
            except Exception:
                continue

            # action_msgs/GoalStatus constants:
            #   0: PENDING, 1: ACTIVE, 2: CANCELING, 3: SUCCEEDED, 4: ABORTED, 5: REJECTED
            status_code = int(getattr(goal_status, "status", -1))
            if status_code == 1:  # ACTIVE
                if goal_uuid_str not in self._sessions:
                    self._sessions[goal_uuid_str] = _SessionState(
                        goal_id=goal_uuid_str, start_time_ros=self._now_ros_sec()
                    )
            elif status_code in (3, 4, 5):  # SUCCEEDED/ABORTED/REJECTED
                session = self._sessions.get(goal_uuid_str)
                if session is None:
                    session = self._extract_session_from_uuid(goal_uuid_str)
                if not session.finalized:
                    self._finalize_session_and_publish(session)
                    # Free session memory after publish (keeps dict bounded).
                    try:
                        del self._sessions[goal_uuid_str]
                    except KeyError:
                        pass

    def _on_action_feedback(self, msg: NavigateToPose_FeedbackMessage) -> None:
        goal_uuid_str = _uuid_to_str(getattr(msg, "goal_id", None))
        if not goal_uuid_str:
            return

        session = self._extract_session_from_uuid(goal_uuid_str)

        feedback = getattr(msg, "feedback", None)
        if feedback is None:
            return

        distance_remaining_m = _safe_float(getattr(feedback, "distance_remaining", None))
        recoveries_count = _safe_int(getattr(feedback, "number_of_recoveries", None))

        current_pose = getattr(feedback, "current_pose", None)
        current_pose_pose = getattr(current_pose, "pose", None) if current_pose is not None else None
        pos = getattr(current_pose_pose, "position", None) if current_pose_pose is not None else None
        current_x = _safe_float(getattr(pos, "x", None)) if pos is not None else None
        current_y = _safe_float(getattr(pos, "y", None)) if pos is not None else None

        if distance_remaining_m is not None:
            if session.optimal_path_len_m is None:
                # First feedback after becoming active gives us a "straight-line" proxy.
                session.optimal_path_len_m = distance_remaining_m
            session.last_distance_remaining_m = distance_remaining_m

        if recoveries_count is not None:
            session.recoveries_count = recoveries_count

        if current_x is not None and current_y is not None:
            if session.last_feedback_xy is not None:
                dx = current_x - session.last_feedback_xy[0]
                dy = current_y - session.last_feedback_xy[1]
                session.actual_path_len_m += math.sqrt(dx * dx + dy * dy)
            session.last_feedback_xy = (current_x, current_y)


def main() -> None:
    import rclpy

    rclpy.init()
    node = PerformanceMonitor()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

