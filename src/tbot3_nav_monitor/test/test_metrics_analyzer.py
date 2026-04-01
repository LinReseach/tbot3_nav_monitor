from __future__ import annotations

import time

from tbot3_nav_monitor.metrics_analyzer import (
    MetricsSample,
    Thresholds,
    assess_degradation,
    choose_overall_alert_level,
    compute_battery_consumption_units,
    compute_obstacle_avoidance_efficiency_ratio,
    compute_recovery_frequency_per_sec,
)


def test_compute_obstacle_avoidance_efficiency_ratio_basic() -> None:
    ratio = compute_obstacle_avoidance_efficiency_ratio(actual_path_len_m=2.0, optimal_path_len_m=1.0)
    assert ratio == 2.0


def test_compute_recovery_frequency_per_sec_zero_time() -> None:
    rf = compute_recovery_frequency_per_sec(number_of_recoveries=3, execution_time_sec=0.0)
    assert rf == 0.0


def test_compute_battery_consumption_units() -> None:
    units = compute_battery_consumption_units(distance_travelled_m=100.0, units_per_meter=0.05)
    assert units == 5.0


def test_assess_degradation_and_alert_level() -> None:
    thresholds = Thresholds(
        recovery_frequency_per_sec_high=0.25,
        navigation_accuracy_m_poor=0.5,
        obstacle_avoidance_efficiency_low_acceptable=1.2,
        battery_consumption_per_km_high=None,
    )

    sample = MetricsSample(
        timestamp_unix=time.time(),
        goal_id="dummy",
        path_execution_time_sec=10.0,
        navigation_accuracy_m=0.6,  # poor
        obstacle_avoidance_efficiency_ratio=1.3,  # inefficient (critical)
        recovery_frequency_per_sec=0.3,  # critical
        battery_consumption_units=0.0,
    )
    degraded = assess_degradation(sample, thresholds)
    assert degraded["recovery_frequency_high"] is True
    assert degraded["navigation_accuracy_poor"] is True
    assert degraded["obstacle_avoidance_inefficient"] is True

    level = choose_overall_alert_level(degraded)
    assert level == "ERROR"

