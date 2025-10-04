from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator

import pytest

from src.detection import (
    barcode_switching,
    inventory_discrepancy,
    queue_health,
    reset_all,
    scanner_avoidance,
    system_health,
    weight_discrepancy,
)
from src.pipeline.transform import SentinelEvent


@pytest.fixture(autouse=True)
def reset_detectors() -> Iterator[None]:
    reset_all()
    yield
    reset_all()


def make_event(
    dataset: str,
    station_id: str,
    timestamp: datetime,
    data: dict | None = None,
    sequence: int | None = None,
) -> SentinelEvent:
    payload = {
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "station_id": station_id,
        "status": "Active",
        "data": data or {},
    }
    raw = {
        "dataset": dataset,
        "sequence": sequence,
        "timestamp": timestamp.isoformat(timespec="seconds"),
        "event": payload,
    }
    return SentinelEvent(
        dataset=dataset,
        timestamp=timestamp,
        station_id=station_id,
        payload=payload,
        sequence=sequence,
        raw=raw,
    )


def test_barcode_switch_detects_mismatch() -> None:
    ts_base = datetime(2025, 8, 13, 16, 0, 5)
    vision_event = make_event(
        "Product_recognism",
        station_id="SCC1",
        timestamp=ts_base,
        data={"predicted_product": "PRD_A_03", "accuracy": 0.8},
    )

    assert barcode_switching.detect_barcode_switching(vision_event) == []

    pos_event = make_event(
        "POS_Transactions",
        station_id="SCC1",
        timestamp=ts_base + timedelta(seconds=4),
        data={"sku": "PRD_F_14", "product_name": "Nestomalt (400g)", "weight_g": 400.0},
        sequence=10,
    )

    alerts = barcode_switching.detect_barcode_switching(pos_event)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["type"] == "barcode_switching"
    assert alert["evidence"]["predicted_product"] == "PRD_A_03"
    assert alert["evidence"]["scanned_sku"] == "PRD_F_14"


def test_scanner_avoidance_triggers_without_recent_pos() -> None:
    ts_base = datetime(2025, 8, 13, 16, 1, 0)
    rfid_event = make_event(
        "RFID_data",
        station_id="SCC1",
        timestamp=ts_base,
        data={"epc": "EPC123", "sku": "PRD_X_01", "location": "OUT_OF_STORE"},
    )

    alerts = scanner_avoidance.detect_scanner_avoidance(rfid_event)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["type"] == "scanner_avoidance"
    assert alert["evidence"]["epc"] == "EPC123"


def test_scanner_avoidance_suppressed_after_pos_scan() -> None:
    ts_base = datetime(2025, 8, 13, 16, 2, 0)
    pos_event = make_event(
        "POS_Transactions",
        station_id="SCC1",
        timestamp=ts_base,
        data={"sku": "PRD_Y_01", "weight_g": 500.0},
    )
    assert scanner_avoidance.detect_scanner_avoidance(pos_event) == []

    rfid_event = make_event(
        "RFID_data",
        station_id="SCC1",
        timestamp=ts_base + timedelta(seconds=5),
        data={"epc": "EPC456", "sku": "PRD_Y_01", "location": "EXIT_GATE"},
    )
    alerts = scanner_avoidance.detect_scanner_avoidance(rfid_event)
    assert alerts == []


def test_weight_discrepancy_flags_large_difference() -> None:
    ts = datetime(2025, 8, 13, 16, 3, 0)
    pos_event = make_event(
        "POS_Transactions",
        station_id="SCC2",
        timestamp=ts,
        data={"sku": "PRD_F_01", "weight_g": 210.0},
        sequence=33,
    )

    alerts = weight_discrepancy.detect_weight_discrepancy(pos_event)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["type"] == "weight_discrepancy"
    assert alert["evidence"]["sku"] == "PRD_F_01"
    assert alert["evidence"]["difference_g"] > 40

    # Second invocation for the same transaction should not duplicate the alert
    alerts_repeat = weight_discrepancy.detect_weight_discrepancy(pos_event)
    assert alerts_repeat == []


def test_queue_health_flags_queue_spike() -> None:
    ts = datetime(2025, 8, 13, 16, 5, 0)
    queue_event = make_event(
        "queue_monitoring",
        station_id="SCC3",
        timestamp=ts,
        data={"customer_count": 9, "average_dwell_time": 75},
    )

    alerts = queue_health.detect_queue_health(queue_event)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["type"] == "queue_spike"
    assert alert["evidence"]["current_queue"] == 9


def test_queue_health_extended_wait_requires_history() -> None:
    ts = datetime(2025, 8, 13, 16, 6, 0)
    base_data = {"average_dwell_time": 150}

    # First two observations should populate history without alerting
    first = make_event("queue_monitoring", "SCC4", ts, data=base_data)
    second = make_event("queue_monitoring", "SCC4", ts + timedelta(seconds=30), data=base_data)
    assert queue_health.detect_queue_health(first) == []
    assert queue_health.detect_queue_health(second) == []

    third = make_event("queue_monitoring", "SCC4", ts + timedelta(minutes=1), data=base_data)
    alerts = queue_health.detect_queue_health(third)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["type"] == "extended_wait"
    assert alert["evidence"]["observations"] >= 3


def test_system_health_emits_and_respects_cooldown() -> None:
    ts = datetime(2025, 8, 13, 16, 7, 0)
    error_event = make_event(
        "system_status",
        station_id="SCC5",
        timestamp=ts,
        data={"status": "Offline", "error_code": "SCAN_FAIL"},
    )
    error_event.payload["status"] = "Offline"
    alerts = system_health.detect_system_health(error_event)
    assert len(alerts) == 1
    assert alerts[0]["type"] == "system_error"

    # Within cooldown -> suppressed
    repeat = make_event(
        "system_status",
        station_id="SCC5",
        timestamp=ts + timedelta(minutes=1),
        data={"status": "offline"},
    )
    repeat.payload["status"] = "offline"
    assert system_health.detect_system_health(repeat) == []

    # Recovery event resets state
    recovery = make_event(
        "system_status",
        station_id="SCC5",
        timestamp=ts + timedelta(minutes=2),
        data={"status": "Active"},
    )
    recovery.payload["status"] = "Active"
    assert system_health.detect_system_health(recovery) == []

    # After cooldown window, new error should alert again
    later = make_event(
        "system_status",
        station_id="SCC5",
        timestamp=ts + timedelta(minutes=5),
        data={"status": "scanner failure"},
    )
    later.payload["status"] = "scanner failure"
    alerts = system_health.detect_system_health(later)
    assert len(alerts) == 1
    assert alerts[0]["type"] == "system_error"


def test_inventory_discrepancy_flags_large_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    inventory_discrepancy.reset_state()
    monkeypatch.setattr(inventory_discrepancy, "_expected_cache", {"PRD_Z_01": 120}, raising=False)

    event = make_event(
        "inventory_snapshots",
        station_id="DC1",
        timestamp=datetime(2025, 8, 13, 16, 8, 0),
        data={"PRD_Z_01": 90},
    )

    alerts = inventory_discrepancy.detect_inventory_discrepancy(event)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["type"] == "inventory_discrepancy"
    assert alert["evidence"]["expected_quantity"] == 120
    assert alert["evidence"]["observed_quantity"] == 90