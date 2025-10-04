"""Queue and dwell-time analytics utilities."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Dict, Iterable, List, Optional, Tuple

from ..pipeline.transform import SentinelEvent

QUEUE_DATASETS = {"Queue_monitor", "queue_monitoring"}


def compute_kpis(events: Iterable[SentinelEvent]) -> dict:
    per_station = defaultdict(list)
    for event in events:
        if event.dataset not in QUEUE_DATASETS:
            continue
        data = event.payload.get("data") or {}
        queue_length = _coerce_float(data.get("customer_count"))
        dwell = _coerce_float(data.get("average_dwell_time"))
        if queue_length is None and dwell is None:
            continue
        per_station[event.station_id or "unknown"].append((event.timestamp, queue_length, dwell))

    if not per_station:
        return {
            "station_kpis": {},
            "avg_queue_length": None,
            "peak_queue_length": None,
            "avg_wait_seconds": None,
            "peak_wait_seconds": None,
            "avg_arrival_rate_per_min": None,
        }

    station_kpis: Dict[str, dict] = {}
    all_queues = []
    all_waits = []
    arrival_rates = []

    for station, series in per_station.items():
        series.sort(key=lambda item: item[0])
        queues = [q for _, q, _ in series if q is not None]
        waits = [w for _, _, w in series if w is not None]

        avg_queue = mean(queues) if queues else None
        peak_queue = max(queues) if queues else None
        avg_wait = mean(waits) if waits else None
        peak_wait = max(waits) if waits else None

        rate = _estimate_arrival_rate(series)
        if rate is not None:
            arrival_rates.append(rate)

        station_kpis[station] = {
            "avg_queue_length": avg_queue,
            "peak_queue_length": peak_queue,
            "avg_wait_seconds": avg_wait,
            "peak_wait_seconds": peak_wait,
            "avg_arrival_rate_per_min": rate,
        }

        all_queues.extend(queues)
        all_waits.extend(waits)

    return {
        "station_kpis": station_kpis,
        "avg_queue_length": mean(all_queues) if all_queues else None,
        "peak_queue_length": max(all_queues) if all_queues else None,
        "avg_wait_seconds": mean(all_waits) if all_waits else None,
        "peak_wait_seconds": max(all_waits) if all_waits else None,
        "avg_arrival_rate_per_min": mean(arrival_rates) if arrival_rates else None,
    }


def _estimate_arrival_rate(series: List[Tuple[datetime, Optional[float], Optional[float]]]) -> Optional[float]:
    pairs = []
    for idx in range(1, len(series)):
        t0, q0, _ = series[idx - 1]
        t1, q1, _ = series[idx]
        if q0 is None or q1 is None:
            continue
        delta_q = q1 - q0
        delta_t = (t1 - t0).total_seconds() / 60  # minutes
        if delta_t <= 0:
            continue
        if delta_q <= 0:
            continue
        pairs.append(delta_q / delta_t)
    if not pairs:
        return None
    return sum(pairs) / len(pairs)


def _coerce_float(value) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
