"""Normalization helpers for Project Sentinel streaming datasets.

This module exposes a small contract for converting heterogeneous raw
payloads into a consistent, analytics-friendly structure.  The
`NormalizedRecord` dataclass captures the canonical schema and keeps the
timestamp as a :class:`datetime.datetime` object for easy sorting before
export.  Conversion utilities support both offline JSONL files (used for
deterministic demo runs) and frames produced by the realtime simulator.

Example
-------
>>> from pathlib import Path
>>> from src.pipeline.transform import iter_jsonl_records
>>> data_root = Path('data/input')
>>> records = list(iter_jsonl_records(data_root / 'pos_transactions.jsonl'))
>>> records[0].dataset
'pos_transactions'

The resulting records can then be enriched with lookup metadata via
``src.pipeline.joiners`` or serialized to JSON with
``NormalizedRecord.to_dict``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional


# ---------------------------------------------------------------------------
# Public data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class NormalizedRecord:
    """Canonical representation of a streaming payload.

    Attributes
    ----------
    dataset:
        Canonical dataset identifier (snake_case, e.g. ``pos_transactions``).
    timestamp:
        Parsed event timestamp as a naive ``datetime`` (source data is in
        local time without an explicit timezone).
    station_id:
        Checkout station identifier when present.
    status:
        Source system status field (e.g. ``"Active"`` for POS events).
    sku:
        Product SKU associated with the event when available.
    customer_id:
        ID of the customer involved in the event when available.
    attributes:
        Dataset-specific payload (deep-copied to avoid mutating inputs).
    metadata:
        Optional auxiliary fields carried alongside the record (e.g.
        stream sequence numbers).  Metadata is not exported by default but
        can be surfaced by callers if required.
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
        """Serialize the record to a JSON-friendly dictionary.

        ``None`` values are omitted to keep the payload compact.
        ``attributes`` are shallow-copied and filtered in the same way.

        Parameters
        ----------
        include_metadata:
            When ``True`` the optional ``metadata`` dictionary is included
            under the ``metadata`` key.
        """

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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_DatasetNormalizer = Callable[[Mapping[str, Any]], NormalizedRecord]


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        raise ValueError(f"Expected ISO timestamp string, got {value!r}")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Invalid ISO timestamp: {value!r}") from exc


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
    return _make_record(
        "inventory_snapshots",
        payload,
        attributes={"inventory": data},
    )


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


DEFAULT_DATASETS: tuple[str, ...] = tuple(
    sorted({alias for alias in _ALIASES.values()})
)


def canonical_dataset(name: str) -> str:
    try:
        return _ALIASES[name]
    except KeyError as exc:  # pragma: no cover - unexpected alias
        raise ValueError(f"Unknown dataset alias: {name}") from exc


def normalize_payload(dataset: str, payload: Mapping[str, Any]) -> NormalizedRecord:
    """Normalize a payload belonging to ``dataset``.

    Parameters
    ----------
    dataset:
        Dataset identifier (any alias accepted).
    payload:
        Mapping containing the raw event payload (as parsed from JSON).
    """

    canonical = canonical_dataset(dataset)
    normalizer = _NORMALIZERS.get(canonical)
    if not normalizer:  # pragma: no cover - sanity guard
        raise ValueError(f"No normalizer registered for dataset {dataset}")
    record = normalizer(payload)
    record.metadata.setdefault("source_dataset", dataset)
    return record


def normalize_stream_frame(frame: Mapping[str, Any]) -> NormalizedRecord:
    """Normalize a frame emitted by the TCP streaming server."""

    dataset = frame.get("dataset")
    if not dataset:
        raise ValueError("Stream frame missing 'dataset'")
    payload = frame.get("event")
    if not isinstance(payload, Mapping):  # pragma: no cover - defensive
        raise ValueError("Stream frame missing 'event' payload")

    record = normalize_payload(dataset, payload)

    # Preserve useful metadata like sequence numbers and original timestamps.
    extras = {
        key: frame[key]
        for key in ("sequence", "original_timestamp", "timestamp")
        if key in frame
    }
    if extras:
        record.metadata.update(extras)
    return record


def iter_jsonl_records(path: Path, *, dataset: Optional[str] = None) -> Iterator[NormalizedRecord]:
    """Read a JSONL file and yield normalized records.

    If ``dataset`` is not provided, the canonical dataset name is inferred
    from the file stem.
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


def load_datasets(
    data_root: Path,
    datasets: Optional[Iterable[str]] = None,
) -> List[NormalizedRecord]:
    """Load and normalize multiple datasets from a directory."""

    target = list(datasets) if datasets else list(DEFAULT_DATASETS)
    records: List[NormalizedRecord] = []
    for name in target:
        canonical = canonical_dataset(name)
        candidate = data_root / f"{canonical}.jsonl"
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        records.extend(iter_jsonl_records(candidate, dataset=canonical))

    return records


__all__ = [
    "DEFAULT_DATASETS",
    "NormalizedRecord",
    "canonical_dataset",
    "iter_jsonl_records",
    "load_datasets",
    "normalize_payload",
    "normalize_stream_frame",
]
