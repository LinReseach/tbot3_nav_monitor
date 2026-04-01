from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Optional

from rclpy.node import Node
from rclpy.qos import QoSProfile
from std_msgs.msg import String

from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_str(x: Any, default: str = "") -> str:
    try:
        return str(x)
    except Exception:
        return default


class DataLogger(Node):
    """
    Logs monitor metrics to CSV.

    Metrics are provided as JSON strings from /tbot3_nav_monitor/metrics.
    """

    def __init__(self) -> None:
        super().__init__("tbot3_nav_monitor_data_logger")

        self.declare_parameter("metrics_topic", "/tbot3_nav_monitor/metrics")
        self.declare_parameter("output_csv", "data/navigation_metrics.csv")
        self.declare_parameter("diagnostics_topic", "/tbot3_nav_monitor/data_logger_diagnostics")
        self.declare_parameter("flush_each_row", True)

        self._metrics_topic: str = str(self.get_parameter("metrics_topic").value)
        self._output_csv: str = str(self.get_parameter("output_csv").value)
        self._diagnostics_topic: str = str(self.get_parameter("diagnostics_topic").value)
        self._flush_each_row: bool = bool(self.get_parameter("flush_each_row").value)

        qos = QoSProfile(depth=10)
        self._sub = self.create_subscription(String, self._metrics_topic, self._on_metrics, qos)
        self._diag_pub = self.create_publisher(DiagnosticArray, self._diagnostics_topic, qos)

        self._csv_path = Path(self._output_csv)
        self._csv_dir = self._csv_path.parent
        self._csv_ready = False

        self._row_count = 0
        self._seen_goal_ids: set = set()

    def _ensure_csv_ready(self) -> None:
        if self._csv_ready:
            return
        self._csv_dir.mkdir(parents=True, exist_ok=True)

        if not self._csv_path.exists():
            with self._csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp_unix",
                        "goal_id",
                        "path_execution_time_sec",
                        "navigation_accuracy_m",
                        "obstacle_avoidance_efficiency_ratio",
                        "recovery_frequency_per_sec",
                        "battery_consumption_units",
                    ]
                )
        self._csv_ready = True

    def _publish_diag(self, message: str, level: int = DiagnosticStatus.OK) -> None:
        diag_array = DiagnosticArray()
        diag_array.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = "tbot3_nav_monitor_data_logger"
        status.level = level
        status.message = message
        diag_array.status.append(status)
        self._diag_pub.publish(diag_array)

    def _on_metrics(self, msg: String) -> None:
        self._ensure_csv_ready()

        try:
            payload = json.loads(msg.data)
        except Exception as e:
            self.get_logger().warning(f"Failed to parse metrics JSON: {e}")
            return

        goal_id = str(payload.get("goal_id", ""))
        if goal_id in self._seen_goal_ids:
            return  # deduplicate repeated deliveries of same goal
        self._seen_goal_ids.add(goal_id)

        row = [
            payload.get("timestamp_unix", 0.0),
            _safe_str(payload.get("goal_id", "")),
            _safe_float(payload.get("path_execution_time_sec", 0.0)),
            _safe_float(payload.get("navigation_accuracy_m", 0.0)),
            _safe_float(payload.get("obstacle_avoidance_efficiency_ratio", 0.0)),
            _safe_float(payload.get("recovery_frequency_per_sec", 0.0)),
            _safe_float(payload.get("battery_consumption_units", 0.0)),
        ]

        try:
            with self._csv_path.open("a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
                if self._flush_each_row:
                    f.flush()
        except Exception as e:
            self.get_logger().error(f"Failed to write CSV row: {e}")
            self._publish_diag(f"CSV write failed: {e}", level=DiagnosticStatus.ERROR)
            return

        self._row_count += 1
        if self._row_count % 10 == 0:
            self._publish_diag(f"Logged {self._row_count} rows to {self._output_csv}")


def main() -> None:
    import rclpy

    rclpy.init()
    node = DataLogger()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()

