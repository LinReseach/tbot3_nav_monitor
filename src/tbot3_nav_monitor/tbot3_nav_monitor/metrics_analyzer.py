from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Thresholds:
    # Recovery
    recovery_frequency_per_sec_high: float = 0.25
    # Navigation accuracy (distance remaining at completion)
    navigation_accuracy_m_poor: float = 0.5
    # Obstacle avoidance efficiency ratio (actual_path_len / optimal_path_len)
    obstacle_avoidance_efficiency_low_acceptable: float = 1.2

    # Battery consumption threshold is optional; used for alerting only.
    battery_consumption_per_km_high: Optional[float] = None


@dataclass(frozen=True)
class MetricsSample:
    # Core
    timestamp_unix: float
    goal_id: str
    path_execution_time_sec: float
    navigation_accuracy_m: float
    obstacle_avoidance_efficiency_ratio: float
    recovery_frequency_per_sec: float
    battery_consumption_units: float


def clamp_ratio(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def compute_obstacle_avoidance_efficiency_ratio(actual_path_len_m: float, optimal_path_len_m: float) -> float:
    """
    Ratio >= 1 indicates extra distance vs an "optimal" straight-line distance.
    """
    if optimal_path_len_m <= 1e-9:
        return float("inf")
    return actual_path_len_m / optimal_path_len_m


def compute_recovery_frequency_per_sec(number_of_recoveries: int, execution_time_sec: float) -> float:
    if execution_time_sec <= 1e-9:
        return 0.0
    return float(number_of_recoveries) / float(execution_time_sec)


def compute_battery_consumption_units(distance_travelled_m: float, units_per_meter: float) -> float:
    # Fictional battery consumption model as requested by the assignment.
    if distance_travelled_m <= 0.0:
        return 0.0
    return distance_travelled_m * units_per_meter


def assess_degradation(m: MetricsSample, thresholds: Thresholds) -> dict[str, bool]:
    """
    Returns flags for degraded performance dimensions.
    """
    degraded = {
        "recovery_frequency_high": m.recovery_frequency_per_sec >= thresholds.recovery_frequency_per_sec_high,
        "navigation_accuracy_poor": m.navigation_accuracy_m >= thresholds.navigation_accuracy_m_poor,
        "obstacle_avoidance_inefficient": (
            m.obstacle_avoidance_efficiency_ratio >= thresholds.obstacle_avoidance_efficiency_low_acceptable
        ),
    }
    if thresholds.battery_consumption_per_km_high is not None:
        # Convert units consumption to per km for thresholding.
        per_km = (m.battery_consumption_units / max(1e-9, m.path_execution_time_sec))  # not perfect; alert only
        degraded["battery_consumption_high"] = per_km >= thresholds.battery_consumption_per_km_high
    else:
        degraded["battery_consumption_high"] = False
    return degraded


def choose_overall_alert_level(degraded_flags: dict[str, bool]) -> str:
    """
    Simple mapping to drive alert severity indicators.
    """
    critical_keys = ["recovery_frequency_high", "obstacle_avoidance_inefficient"]
    warning_keys = ["navigation_accuracy_poor"]

    if any(degraded_flags.get(k, False) for k in critical_keys):
        return "ERROR"
    if any(degraded_flags.get(k, False) for k in warning_keys):
        return "WARN"
    return "OK"

