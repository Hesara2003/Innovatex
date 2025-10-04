"""Detect unexpected system crashes and scanning errors from status signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..pipeline.transform import SentinelEvent

ERROR_KEYWORDS = {"error", "offline", "crash", "failure", "fault"}
COOLDOWN = timedelta(minutes=3)


@dataclass(slots=True)
class HealthState:
    last_alert: Optional[datetime] = None
    recovered: bool = True


_health_state: Dict[tuple[str, str | None], HealthState] = {}


def reset_state() -> None:
    _health_state.clear()


def detect_system_health(event: SentinelEvent) -> List[dict]:
    status = _normalise_status(event.payload.get("status"))
    data = event.payload.get("data")
    if isinstance(data, dict) and status is None:
        status = _normalise_status(data.get("status"))

    # Additional error hints inside data payload
    error_code = None
    if isinstance(data, dict):
        for key in ("error_code", "scan_error", "scan_status", "scanner_state"):
            if key in data:
                raw = data[key]
                error_code = str(raw)
                if isinstance(raw, str) and not raw.lower().startswith("ok"):
                    status = status or "error"
                break

    key = (event.dataset, event.station_id)
    state = _health_state.setdefault(key, HealthState())

    if status is None:
        # No explicit status issues; mark recovered to allow future alerts.
        state.recovered = True
        return []

    if not _is_error_status(status) and error_code is None:
        state.recovered = True
        return []

    now = event.timestamp
    if state.last_alert and now - state.last_alert < COOLDOWN:
        return []

    state.last_alert = now
    state.recovered = False

    return [
        {
            "type": "system_error",
            "station_id": event.station_id,
            "timestamp": now.isoformat(timespec="milliseconds"),
            "confidence": 0.85,
            "evidence": {
                "dataset": event.dataset,
                "status": status,
                "error_code": error_code,
            },
            "recommended_action": "Dispatch technician to inspect scanner and restart service pipeline.",
        }
    ]


def _normalise_status(value) -> Optional[str]:
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed:
            return trimmed
    return None


def _is_error_status(status: str) -> bool:
    lowered = status.lower()
    if lowered in {"active", "ok", "ready", "online"}:
        return False
    return any(keyword in lowered for keyword in ERROR_KEYWORDS)
