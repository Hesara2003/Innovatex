"""Detect inventory discrepancies between expected and observed stock levels."""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from ..pipeline.transform import SentinelEvent

INVENTORY_DATASETS = {"Current_inventory_data", "inventory_snapshots"}
COOLDOWN = timedelta(minutes=10)
ABS_THRESHOLD = 8
REL_THRESHOLD = 0.12

_expected_cache: Dict[str, int] | None = None
_last_alert: Dict[str, datetime] = {}


def reset_state() -> None:
    global _expected_cache
    _expected_cache = None
    _last_alert.clear()


def detect_inventory_discrepancy(event: SentinelEvent) -> List[dict]:
    if event.dataset not in INVENTORY_DATASETS:
        return []

    observed = event.payload.get("data")
    if not isinstance(observed, dict):
        return []

    expected = _load_expected()
    now = event.timestamp
    alerts: List[dict] = []

    for sku, observed_value in observed.items():
        try:
            observed_qty = int(observed_value)
        except (ValueError, TypeError):
            continue

        expected_qty = expected.get(sku)
        if expected_qty is None:
            continue

        diff = observed_qty - expected_qty
        if abs(diff) < max(ABS_THRESHOLD, int(expected_qty * REL_THRESHOLD)):
            continue

        last = _last_alert.get(sku)
        if last and now - last < COOLDOWN:
            continue

        _last_alert[sku] = now
        alerts.append(
            {
                "type": "inventory_discrepancy",
                "station_id": event.station_id,
                "timestamp": now.isoformat(timespec="milliseconds"),
                "confidence": min(0.99, 0.6 + abs(diff) / max(1, expected_qty)),
                "evidence": {
                    "sku": sku,
                    "expected_quantity": expected_qty,
                    "observed_quantity": observed_qty,
                    "difference": diff,
                },
                "recommended_action": "Audit shelf and backroom counts for SKU and reconcile with POS adjustments.",
            }
        )

    return alerts


def _load_expected() -> Dict[str, int]:
    global _expected_cache
    if _expected_cache is not None:
        return _expected_cache

    repo_root = Path(__file__).resolve().parents[2]
    catalog_path = repo_root / "data" / "input" / "products_list.csv"
    expected: Dict[str, int] = {}
    if catalog_path.exists():
        with catalog_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                sku = row.get("SKU")
                qty = row.get("quantity")
                if not sku or qty is None:
                    continue
                try:
                    expected[sku] = int(float(qty))
                except ValueError:
                    continue
    _expected_cache = expected
    return expected
