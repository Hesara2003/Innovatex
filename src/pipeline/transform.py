"""Utilities to normalize incoming JSONL payloads into typed events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class SentinelEvent:
    """Canonical representation of a record emitted by the stream server."""

    dataset: str
    timestamp: datetime
    station_id: str | None
    payload: dict[str, Any]
    sequence: int | None = None
    raw: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict for downstream consumers."""

        base = {
            "dataset": self.dataset,
            "timestamp": self.timestamp.isoformat(timespec="milliseconds"),
            "station_id": self.station_id,
            "sequence": self.sequence,
            "payload": self.payload,
        }
        if self.raw is not None:
            base["raw"] = self.raw
        return base


def normalize_event(raw_line: bytes) -> SentinelEvent | None:
    """Parse a newline-delimited JSON frame into :class:`SentinelEvent`.

    The TCP stream begins with an informational banner that does not contain a
    ``dataset`` field; in that case ``None`` is returned so callers can ignore
    it gracefully.
    """

    try:
        obj = json.loads(raw_line)
    except json.JSONDecodeError:
        return None

    dataset = obj.get("dataset")
    if not isinstance(dataset, str):
        return None

    payload = obj.get("event")
    if not isinstance(payload, dict):
        payload = {}

    timestamp_str = obj.get("timestamp") or payload.get("timestamp")
    if not isinstance(timestamp_str, str):
        return None

    try:
        timestamp = datetime.fromisoformat(timestamp_str)
    except ValueError:
        return None

    station_id = payload.get("station_id")
    if station_id is not None and not isinstance(station_id, str):
        station_id = str(station_id)

    return SentinelEvent(
        dataset=dataset,
        timestamp=timestamp,
        station_id=station_id,
        payload=payload,
        sequence=obj.get("sequence") if isinstance(obj.get("sequence"), int) else None,
        raw=obj,
    )
