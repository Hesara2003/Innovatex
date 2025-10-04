"""Weight discrepancy detector driven by POS vs catalog weights."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from ..pipeline.transform import SentinelEvent

POS_DATASETS = {"POS_Transactions", "pos_transactions"}

ABS_TOLERANCE_GRAMS = 8.0
REL_TOLERANCE = 0.08  # ±8 % window


@dataclass(slots=True)
class CatalogEntry:
    sku: str
    product_name: Optional[str]
    expected_weight_g: Optional[float]
    price: Optional[float]


_flagged_transactions: set[tuple[str | None, str | None, str | None]] = set()


def reset_state() -> None:
    _flagged_transactions.clear()


def detect_weight_discrepancy(event: SentinelEvent) -> List[dict]:
    if event.dataset not in POS_DATASETS:
        return []

    pos_data = event.payload.get("data", {})
    sku = pos_data.get("sku") if isinstance(pos_data.get("sku"), str) else None
    measured_weight = _coerce_float(pos_data.get("weight_g") or pos_data.get("weight"))

    if not sku or measured_weight is None:
        return []

    catalog_entry = _catalog().get(sku)
    if not catalog_entry or catalog_entry.expected_weight_g is None:
        return []

    expected_weight = catalog_entry.expected_weight_g
    diff = abs(measured_weight - expected_weight)
    tolerance = max(ABS_TOLERANCE_GRAMS, expected_weight * REL_TOLERANCE)

    if diff <= tolerance:
        return []

    key = (event.station_id, event.timestamp.isoformat(timespec="milliseconds"), sku)
    if key in _flagged_transactions:
        return []

    deviation = diff / expected_weight if expected_weight else 0.0
    confidence = round(min(0.99, 0.6 + deviation), 2)

    alert = {
        "type": "weight_discrepancy",
        "station_id": event.station_id,
        "timestamp": event.timestamp.isoformat(timespec="milliseconds"),
        "confidence": confidence,
        "evidence": {
            "sku": sku,
            "product_name": catalog_entry.product_name,
            "measured_weight_g": measured_weight,
            "expected_weight_g": expected_weight,
            "difference_g": round(diff, 2),
            "price": catalog_entry.price,
        },
    }

    _flagged_transactions.add(key)
    return [alert]


def _catalog() -> Dict[str, CatalogEntry]:
    return _load_catalog()


@lru_cache(maxsize=1)
def _load_catalog() -> Dict[str, CatalogEntry]:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_path = repo_root / "data" / "input" / "products_list.csv"

    catalog: Dict[str, CatalogEntry] = {}
    if not catalog_path.exists():
        return catalog

    with catalog_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sku = row.get("SKU")
            if not sku:
                continue
            weight = _coerce_float(row.get("weight"))
            price = _coerce_float(row.get("price"))
            catalog[sku] = CatalogEntry(
                sku=sku,
                product_name=row.get("product_name"),
                expected_weight_g=weight,
                price=price,
            )
    return catalog


def _coerce_float(value) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
