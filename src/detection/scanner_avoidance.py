"""Scanner avoidance detector using RFID and POS fusion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..pipeline.transform import SentinelEvent

POS_DATASETS = {"POS_Transactions", "pos_transactions"}
RFID_DATASETS = {"RFID_data", "rfid_readings"}

SUSPICIOUS_LOCATIONS = {
    "EXIT_GATE",
    "EXIT_LANE",
    "CUSTOMER_EXIT",
    "OUT_OF_STORE",
    "BAGGING_AREA_BREACH",
    "UNKNOWN",
}

RECENT_SCAN_WINDOW = timedelta(seconds=25)
RFID_TTL = timedelta(seconds=60)
ALERT_COOLDOWN = timedelta(seconds=30)


@dataclass(slots=True)
class RFIDObservation:
    sku: Optional[str]
    location: str
    timestamp: datetime


_recent_pos_by_sku: Dict[str, datetime] = {}
_recent_rfid_by_epc: Dict[str, RFIDObservation] = {}
_alert_cooldown: Dict[str, datetime] = {}


def reset_state() -> None:
    """Clear cached RFID/POS data (for tests)."""

    _recent_pos_by_sku.clear()
    _recent_rfid_by_epc.clear()
    _alert_cooldown.clear()


def detect_scanner_avoidance(event: SentinelEvent) -> List[dict]:
    station_id = event.station_id or "unknown"
    now = event.timestamp

    _expire_old_records(now)

    if event.dataset in POS_DATASETS:
        pos_data = event.payload.get("data", {})
        sku = pos_data.get("sku")
        if isinstance(sku, str):
            _recent_pos_by_sku[sku] = now
        return []

    if event.dataset not in RFID_DATASETS:
        return []

    rfid_data = event.payload.get("data", {})
    epc = rfid_data.get("epc")
    location = rfid_data.get("location")
    sku = rfid_data.get("sku")

    if not isinstance(epc, str) or not isinstance(location, str):
        return []

    observation = RFIDObservation(
        sku=sku if isinstance(sku, str) else None,
        location=location.upper(),
        timestamp=now,
    )
    _recent_rfid_by_epc[epc] = observation

    if observation.location not in SUSPICIOUS_LOCATIONS:
        return []

    last_scan_time = _recent_pos_by_sku.get(observation.sku or "") if observation.sku else None

    if last_scan_time and now - last_scan_time <= RECENT_SCAN_WINDOW:
        return []

    if not _should_emit_alert(epc, now):
        return []

    confidence = 0.75
    if observation.location in {"CUSTOMER_EXIT", "OUT_OF_STORE"}:
        confidence = 0.9

    alert = {
        "type": "scanner_avoidance",
        "station_id": station_id,
        "timestamp": now.isoformat(timespec="milliseconds"),
        "confidence": confidence,
        "evidence": {
            "epc": epc,
            "sku": observation.sku,
            "location": observation.location,
            "last_pos_scan_ts": last_scan_time.isoformat(timespec="milliseconds") if last_scan_time else None,
        },
    }

    _alert_cooldown[epc] = now
    return [alert]


def _expire_old_records(reference_time: datetime) -> None:
    expired_skus = [sku for sku, ts in _recent_pos_by_sku.items() if reference_time - ts > RECENT_SCAN_WINDOW]
    for sku in expired_skus:
        _recent_pos_by_sku.pop(sku, None)

    expired_epc = [epc for epc, obs in _recent_rfid_by_epc.items() if reference_time - obs.timestamp > RFID_TTL]
    for epc in expired_epc:
        _recent_rfid_by_epc.pop(epc, None)

    cooldown_expired = [epc for epc, ts in _alert_cooldown.items() if reference_time - ts > ALERT_COOLDOWN]
    for epc in cooldown_expired:
        _alert_cooldown.pop(epc, None)


def _should_emit_alert(epc: str, reference_time: datetime) -> bool:
    last_alert = _alert_cooldown.get(epc)
    if last_alert is None:
        return True
    return reference_time - last_alert > ALERT_COOLDOWN
