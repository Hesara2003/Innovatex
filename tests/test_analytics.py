from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.analytics.queue_metrics import QueueMetricsService, compute_kpis
from src.analytics.operations import generate_insights
from src.pipeline.transform import SentinelEvent


def make_event(
    timestamp: datetime,
    station_id: str,
    queue_length: float | int | None,
    dwell_time: float | int | None,
) -> SentinelEvent:
    payload = {
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "station_id": station_id,
        "status": "Active",
        "data": {},
    }
    if queue_length is not None:
        payload["data"]["customer_count"] = queue_length
    if dwell_time is not None:
        payload["data"]["average_dwell_time"] = dwell_time

    return SentinelEvent(
        dataset="queue_monitoring",
        timestamp=timestamp,
        station_id=station_id,
        payload=payload,
    )


def test_compute_kpis_with_single_station() -> None:
    base = datetime(2025, 8, 13, 16, 10, 0)
    events = [
        make_event(base, "SCC1", queue_length=4, dwell_time=90),
        make_event(base + timedelta(minutes=1), "SCC1", queue_length=7, dwell_time=150),
        make_event(base + timedelta(minutes=2), "SCC1", queue_length=9, dwell_time=180),
    ]

    kpis = compute_kpis(events)
    station = kpis["station_kpis"]["SCC1"]

    assert station["avg_queue_length"] == pytest.approx(20 / 3, rel=1e-4)
    assert station["peak_queue_length"] == 9
    assert station["avg_wait_seconds"] == pytest.approx(140, rel=1e-3)
    assert station["peak_wait_seconds"] == 180
    assert station["avg_arrival_rate_per_min"] == pytest.approx(2.5, rel=1e-4)

    assert kpis["avg_queue_length"] == pytest.approx(20 / 3, rel=1e-4)
    assert kpis["peak_queue_length"] == 9
    assert kpis["avg_wait_seconds"] == pytest.approx(140, rel=1e-3)
    assert kpis["peak_wait_seconds"] == 180
    assert kpis["avg_arrival_rate_per_min"] == pytest.approx(2.5, rel=1e-4)


def test_generate_insights_combines_kpis_and_detections() -> None:
    base = datetime(2025, 8, 13, 17, 0, 0)
    events = [
        make_event(base, "SCC2", queue_length=5, dwell_time=150),
        make_event(base + timedelta(minutes=1), "SCC2", queue_length=7, dwell_time=165),
        make_event(base + timedelta(minutes=2), "SCC2", queue_length=9, dwell_time=170),
    ]

    detections = [
        {"type": "system_error", "evidence": {}},
        {"type": "inventory_discrepancy", "evidence": {"sku": "PRD_Z_01"}},
    ]

    insights = generate_insights(events, detections)

    assert insights["staffing"]["recommended_associates"] == 3
    assert insights["kiosk_plan"]["recommended_kiosks"] == 2

    messages = insights["additional_insights"]
    assert any("Extend associate coverage" in msg for msg in messages)
    assert any("Schedule preventive maintenance" in msg for msg in messages)
    assert any("Inventory mismatch detected" in msg for msg in messages)
    assert len(messages) == 3


def test_compute_kpis_with_no_queue_data() -> None:
    kpis = compute_kpis([])
    assert kpis["station_kpis"] == {}
    assert all(kpis[key] is None for key in ("avg_queue_length", "peak_queue_length", "avg_wait_seconds", "peak_wait_seconds", "avg_arrival_rate_per_min"))


def test_generate_insights_without_queue_events() -> None:
    events: list[SentinelEvent] = []
    detections: list[dict] = []
    insights = generate_insights(events, detections)

    assert insights["staffing"]["recommended_associates"] is None
    assert insights["kiosk_plan"]["recommended_kiosks"] is None
    assert insights["additional_insights"] == [
        "Operations running within targets. Continue monitoring real-time dashboards for anomalies."
    ]


def test_queue_health_flags_multiple_risk_factors_and_incidents() -> None:
    service = QueueMetricsService(target_customers_per_station=4, history_length=12)
    base = datetime(2025, 8, 13, 18, 0, 0)

    service.ingest_observation(
        "REG1",
        {
            "timestamp": base.isoformat(),
            "customer_count": 4,
            "average_dwell_time": 180,
            "service_rate": 3.2,
        },
    )

    health = service.ingest_observation(
        "REG1",
        {
            "timestamp": (base + timedelta(minutes=1)).isoformat(),
            "customer_count": 9,
            "average_dwell_time": 520,
            "service_rate": 0.4,
        },
    )

    alert_types = {alert["type"] for alert in health["alerts"]}
    assert health["health_score"] < 50
    assert health["status"] == "critical"
    assert {"dwell_time_critical", "queue_congestion", "service_rate_low", "queue_growth"}.issubset(alert_types)

    incidents = service.get_recent_incidents()
    incident_types = {incident["type"] for incident in incidents}
    assert "queue_surge" in incident_types
    assert "extreme_wait" in incident_types


def test_staff_allocation_recommends_more_stations_when_overloaded() -> None:
    service = QueueMetricsService(target_customers_per_station=5)
    base = datetime(2025, 8, 13, 19, 0, 0)

    service.ingest_observation(
        "REG_A",
        {
            "timestamp": base.isoformat(),
            "customer_count": 12,
            "average_dwell_time": 210,
        },
    )
    service.ingest_observation(
        "REG_B",
        {
            "timestamp": (base + timedelta(seconds=30)).isoformat(),
            "customer_count": 11,
            "average_dwell_time": 240,
        },
    )

    allocation = service.calculate_staff_allocation()

    assert allocation["active_stations"] == 2
    assert allocation["required_stations"] == 5
    assert allocation["total_customers"] == 23
    assert allocation["recommendation"].startswith("Open 3 additional station")
