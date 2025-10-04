"""Merged normalization utilities for Project Sentinel.

This module unifies two previous implementations:
- a rich NormalizedRecord-based normalizer (file-oriented and frame-oriented),
- a lightweight SentinelEvent parser for raw stream frames.

The file provides helpers to parse JSONL files, parse raw TCP stream frames,
convert them into a SentinelEvent and/or NormalizedRecord, and export a
small, predictable public API for downstream analytics.

If you want the file split into `realtime.py` and `batch.py` or need
pytest tests, tell me and I'll create them in the canvas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple


# -----------------------------
# Robust timestamp parsing
# -----------------------------

def _parse_timestamp(value: Any) -> datetime:
    """Best-effort ISO-8601 parsing with common fallbacks.

    Accepts datetime objects or ISO-like strings (with or without "Z").
    Falls back to :class:`ValueError` for invalid input so callers may
    decide how to recover.
    """
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Expected ISO timestamp string or datetime, got {value!r}")
    try:
        # accept trailing Z as UTC
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid ISO timestamp: {value!r}") from exc


# -----------------------------
# SentinelEvent (stream parser)
# -----------------------------

@dataclass(slots=True)
class SentinelEvent:
    """Canonical representation of a record emitted by the stream server.

    Fields are intentionally minimal: downstream code may convert a
    SentinelEvent into a richer NormalizedRecord.
    """

    dataset: str
    timestamp: datetime
    station_id: Optional[str]
    payload: Dict[str, Any]
    sequence: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None

    def as_dict(self) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "dataset": self.dataset,
            "timestamp": self.timestamp.isoformat(timespec="milliseconds"),
            "station_id": self.station_id,
            "sequence": self.sequence,
            "payload": self.payload,
        }
        if self.raw is not None:
            base["raw"] = self.raw
        return base


def normalize_event(raw_line: bytes) -> Optional[SentinelEvent]:
    """Parse a raw newline-delimited JSON frame into a SentinelEvent.

    Returns ``None`` for non-JSON frames or frames that do not contain a
    valid dataset/timestamp. Callers should ignore ``None`` results.
    """
    try:
        obj = json.loads(raw_line)
    except Exception:
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
        timestamp = _parse_timestamp(timestamp_str)
    except ValueError:
        return None

    station_id = payload.get("station_id")
    if station_id is not None and not isinstance(station_id, str):
        station_id = str(station_id)

    seq = obj.get("sequence") if isinstance(obj.get("sequence"), int) else None

    return SentinelEvent(
        dataset=dataset,
        timestamp=timestamp,
        station_id=station_id,
        payload=payload,
        sequence=seq,
        raw=obj,
    )


# -----------------------------
# NormalizedRecord (analytics-friendly)
# -----------------------------

@dataclass(slots=True)
class NormalizedRecord:
    """Canonical representation of a streaming payload used by analytics.

    This mirrors the earlier NormalizedRecord contract and keeps the
    timestamp as a ``datetime`` for easy sorting and grouping.
    """

    dataset: str
    timestamp: datetime
    station_id: Optional[str]
    status: Optional[str]
    sku: Optional[str]
    customer_id: Optional[str]
    attributes: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_metadata: bool = False) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "dataset": self.dataset,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.station_id is not None:
            base["station_id"] = self.station_id
        if self.status is not None:
            base["status"] = self.status
        if self.sku is not None:
            base["sku"] = self.sku
        if self.customer_id is not None:
            base["customer_id"] = self.customer_id
        if self.attributes:
            attrs = {k: v for k, v in self.attributes.items() if v is not None}
            if attrs:
                base["attributes"] = attrs
        if include_metadata and self.metadata:
            base["metadata"] = dict(self.metadata)
        return base


# -----------------------------
# Dataset normalizers
# -----------------------------

_DatasetNormalizer = Callable[[Mapping[str, Any]], NormalizedRecord]


def _copy_payload(data: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    return dict(data or {})


def _make_record(
    dataset: str,
    payload: Mapping[str, Any],
    *,
    station_id: Optional[str] = None,
    status: Optional[str] = None,
    sku: Optional[str] = None,
    customer_id: Optional[str] = None,
    attributes: Optional[Mapping[str, Any]] = None,
) -> NormalizedRecord:
    return NormalizedRecord(
        dataset=dataset,
        timestamp=_parse_timestamp(payload.get("timestamp")),
        station_id=station_id,
        status=status,
        sku=sku,
        customer_id=customer_id,
        attributes=_copy_payload(attributes),
    )


def _normalize_inventory(payload: Mapping[str, Any]) -> NormalizedRecord:
    data = _copy_payload(payload.get("data"))
    return _make_record("inventory_snapshots", payload, attributes={"inventory": data})


def _normalize_queue(payload: Mapping[str, Any]) -> NormalizedRecord:
    data = _copy_payload(payload.get("data"))
    return _make_record(
        "queue_monitoring",
        payload,
        station_id=payload.get("station_id"),
        status=payload.get("status"),
        attributes=data,
    )


def _normalize_product_recognition(payload: Mapping[str, Any]) -> NormalizedRecord:
    data = _copy_payload(payload.get("data"))
    sku = data.get("predicted_product")
    return _make_record(
        "product_recognition",
        payload,
        station_id=payload.get("station_id"),
        status=payload.get("status"),
        sku=sku,
        attributes=data,
    )


def _normalize_pos(payload: Mapping[str, Any]) -> NormalizedRecord:
    data = _copy_payload(payload.get("data"))
    return _make_record(
        "pos_transactions",
        payload,
        station_id=payload.get("station_id"),
        status=payload.get("status"),
        sku=data.get("sku"),
        customer_id=data.get("customer_id"),
        attributes=data,
    )


def _normalize_rfid(payload: Mapping[str, Any]) -> NormalizedRecord:
    data = _copy_payload(payload.get("data"))
    return _make_record(
        "rfid_readings",
        payload,
        station_id=payload.get("station_id"),
        status=payload.get("status"),
        sku=data.get("sku"),
        attributes=data,
    )


_NORMALIZERS: Dict[str, _DatasetNormalizer] = {
    "inventory_snapshots": _normalize_inventory,
    "queue_monitoring": _normalize_queue,
    "product_recognition": _normalize_product_recognition,
    "pos_transactions": _normalize_pos,
    "rfid_readings": _normalize_rfid,
}


_ALIASES: Dict[str, str] = {
    "inventory_snapshots": "inventory_snapshots",
    "Current_inventory_data": "inventory_snapshots",
    "queue_monitoring": "queue_monitoring",
    "Queue_monitor": "queue_monitoring",
    "product_recognition": "product_recognition",
    "Product_recognism": "product_recognition",
    "pos_transactions": "pos_transactions",
    "POS_Transactions": "pos_transactions",
    "rfid_readings": "rfid_readings",
    "RFID_data": "rfid_readings",
}


DEFAULT_DATASETS: Tuple[str, ...] = tuple(sorted({alias for alias in _ALIASES.values()}))


def canonical_dataset(name: str) -> str:
    try:
        return _ALIASES[name]
    except KeyError as exc:  # pragma: no cover - unexpected alias
        raise ValueError(f"Unknown dataset alias: {name}") from exc


def normalize_payload(dataset: str, payload: Mapping[str, Any]) -> NormalizedRecord:
    """Normalize a raw payload belonging to ``dataset`` into NormalizedRecord.

    Accepts any alias for ``dataset`` (as defined in ``_ALIASES``).
    """

    canonical = canonical_dataset(dataset)
    normalizer = _NORMALIZERS.get(canonical)
    if not normalizer:  # pragma: no cover - sanity guard
        raise ValueError(f"No normalizer registered for dataset {dataset}")
    record = normalizer(payload)
    record.metadata.setdefault("source_dataset", dataset)
    return record


def normalize_stream_frame(frame: Mapping[str, Any]) -> NormalizedRecord:
    """Normalize a streaming frame (dictionary) into a NormalizedRecord.

    This accepts the same frames produced by the stream server (a mapping
    with keys like ``dataset`` and ``event``).  It preserves a subset of
    useful metadata (sequence, original timestamp).
    """
    dataset = frame.get("dataset")
    if not dataset:
        raise ValueError("Stream frame missing 'dataset'")
    payload = frame.get("event")
    if not isinstance(payload, Mapping):  # pragma: no cover - defensive
        raise ValueError("Stream frame missing 'event' payload")

    record = normalize_payload(dataset, payload)

    extras = {k: frame[k] for k in ("sequence", "original_timestamp", "timestamp") if k in frame}
    if extras:
        record.metadata.update(extras)
    return record


def sentinel_to_normalized(event: SentinelEvent) -> NormalizedRecord:
    """Convenience converter: SentinelEvent -> NormalizedRecord.

    Uses ``event.payload`` as the payload argument to the regular
    normalizers.  Adds minimal metadata (sequence, raw frame) for tracing.
    """
    record = normalize_payload(event.dataset, event.payload)
    if event.sequence is not None:
        record.metadata["sequence"] = event.sequence
    if event.raw is not None:
        record.metadata["raw_frame"] = event.raw
    return record


# -----------------------------
# File helpers
# -----------------------------


def iter_jsonl_records(path: Path, *, dataset: Optional[str] = None) -> Iterator[NormalizedRecord]:
    """Read a JSONL file and yield normalized records.

    If ``dataset`` is omitted the canonical dataset name is inferred from
    the file stem and resolved via the alias map.
    """
    if dataset is None:
        dataset = canonical_dataset(path.stem)

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            yield normalize_payload(dataset, payload)


def load_datasets(data_root: Path, datasets: Optional[Iterable[str]] = None) -> List[NormalizedRecord]:
    """Load and normalize multiple datasets from a directory.

    Raises :class:`FileNotFoundError` if expected dataset files are missing.
    """
    target = list(datasets) if datasets else list(DEFAULT_DATASETS)
    records: List[NormalizedRecord] = []
    for name in target:
        canonical = canonical_dataset(name)
        candidate = data_root / f"{canonical}.jsonl"
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        records.extend(iter_jsonl_records(candidate, dataset=canonical))
    return records


# -----------------------------
# Public API
# -----------------------------

__all__ = [
    "SentinelEvent",
    "normalize_event",
    "NormalizedRecord",
    "normalize_payload",
    "normalize_stream_frame",
    "sentinel_to_normalized",
    "iter_jsonl_records",
    "load_datasets",
    "canonical_dataset",
    "DEFAULT_DATASETS",
]
