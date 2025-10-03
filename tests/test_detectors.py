from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator

import pytest

from src.detection import barcode_switching, reset_all, scanner_avoidance, weight_discrepancy
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