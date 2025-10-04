"""Detect long queue lengths and prolonged wait times."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Deque, Dict, List

from ..pipeline.transform import SentinelEvent

QUEUE_DATASETS = {"Queue_monitor", "queue_monitoring"}
MAX_QUEUE_TARGET = 6
MAX_WAIT_SECONDS = 120
WINDOW = timedelta(minutes=5)
MIN_OBSERVATIONS = 3

_recent_waits: Dict[str, Deque[tuple[datetime, float]]] = {}
_recent_queues: Dict[str, Deque[tuple[datetime, int]]] = {}
_last_alert_queue: Dict[str, datetime] = {}
_last_alert_wait: Dict[str, datetime] = {}
COOLDOWN = timedelta(minutes=2)


def reset_state() -> None:
    _recent_waits.clear()
    _recent_queues.clear()
    _last_alert_queue.clear()
    _last_alert_wait.clear()


def detect_queue_health(event: SentinelEvent) -> List[dict]:
    if event.dataset not in QUEUE_DATASETS:
        return []

    station_id = event.station_id or "unknown"
    now = event.timestamp
    data = event.payload.get("data") or {}

    queue_length = _coerce_int(data.get("customer_count"))
    dwell_time = _coerce_float(data.get("average_dwell_time"))

    alerts: List[dict] = []

    if queue_length is not None:
        alerts.extend(_process_queue_length(station_id, now, queue_length))
    if dwell_time is not None:
        alerts.extend(_process_wait_time(station_id, now, dwell_time))

    return alerts


def _process_queue_length(station_id: str, now: datetime, queue_length: int) -> List[dict]:
    series = _recent_queues.setdefault(station_id, deque())
    series.append((now, queue_length))
    _trim_window(series, now)

    if queue_length < MAX_QUEUE_TARGET:
        return []

    last_alert = _last_alert_queue.get(station_id)
    if last_alert and now - last_alert < COOLDOWN:
        return []

    recent_avg = sum(length for _, length in series) / len(series)
    _last_alert_queue[station_id] = now
    return [
        {
            "type": "queue_spike",
            "station_id": station_id,
            "timestamp": now.isoformat(timespec="milliseconds"),
            "confidence": min(0.95, 0.6 + (queue_length - MAX_QUEUE_TARGET) * 0.08),
            "evidence": {
                "current_queue": queue_length,
                "recent_average": round(recent_avg, 2),
                "target_queue": MAX_QUEUE_TARGET,
            },
            "recommended_action": "Open an additional kiosk or direct staff assistance to self-checkout lane.",
        }
    ]


def _process_wait_time(station_id: str, now: datetime, dwell_time: float) -> List[dict]:
    series = _recent_waits.setdefault(station_id, deque())
    series.append((now, dwell_time))
    _trim_window(series, now)

    if len(series) < MIN_OBSERVATIONS:
        return []

    avg_wait = sum(value for _, value in series) / len(series)
    if avg_wait < MAX_WAIT_SECONDS:
        return []

    last_alert = _last_alert_wait.get(station_id)
    if last_alert and now - last_alert < COOLDOWN:
        return []

    _last_alert_wait[station_id] = now
    return [
        {
            "type": "extended_wait",
            "station_id": station_id,
            "timestamp": now.isoformat(timespec="milliseconds"),
            "confidence": min(0.99, 0.7 + (avg_wait - MAX_WAIT_SECONDS) / 180),
            "evidence": {
                "recent_average_wait_s": round(avg_wait, 1),
                "threshold_s": MAX_WAIT_SECONDS,
                "observations": len(series),
            },
            "recommended_action": "Reassign associates to assist with bagging or open more kiosks to reduce dwell time.",
        }
    ]


def _trim_window(series: Deque[tuple[datetime, float]], now: datetime) -> None:
    while series and now - series[0][0] > WINDOW:
        series.popleft()


def _coerce_float(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _coerce_int(value) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None
