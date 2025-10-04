"""Inventory analytics for Project Sentinel (standard-library only)."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


class InventoryAnalyzer:
    """Detect shrinkage, flag high-value risks, and forecast expectations."""

    def __init__(
        self,
        data_root: Optional[Path] = None,
        high_value_threshold: float = 750.0,
    ) -> None:
        self.high_value_threshold = high_value_threshold
        self._catalog: Optional[Dict[str, Dict[str, object]]] = None
        self._data_root = Path(data_root) if data_root else Path(__file__).resolve().parents[2] / "data" / "input"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(
        self,
        baseline_inventory: Dict[str, int],
        actual_inventory: Dict[str, int],
        sales_events: Iterable[Dict[str, object]],
        restock_events: Optional[Iterable[Dict[str, object]]] = None,
    ) -> Dict[str, object]:
        """High-level inventory analysis suitable for dashboards."""

        shrinkage = self.calculate_inventory_shrinkage(
            baseline_inventory,
            actual_inventory,
            sales_events,
            restock_events,
        )

        catalog = self._load_catalog()
        high_value_watch = self._high_value_watch(actual_inventory, catalog)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_shrinkage_value": shrinkage["totals"]["shrinkage_value"],
                "total_shrinkage_units": shrinkage["totals"]["shrinkage_units"],
                "overall_expected_value": shrinkage["totals"]["expected_value"],
                "overall_actual_value": shrinkage["totals"]["actual_value"],
            },
            "skus": shrinkage["per_sku"],
            "alerts": {
                "shrinkage": shrinkage["alerts"],
                "high_value_watch": high_value_watch,
            },
        }

    # @algorithm ShrinkageDetection | Calculate inventory shrinkage( these arent implemented yet)
    def calculate_inventory_shrinkage(
        self,
        baseline_inventory: Dict[str, int],
        actual_inventory: Dict[str, int],
        sales_events: Iterable[Dict[str, object]],
        restock_events: Optional[Iterable[Dict[str, object]]] = None,
    ) -> Dict[str, object]:
        """Calculate shrinkage after accounting for sales and restocks."""

        catalog = self._load_catalog()
        sales_counter = self._aggregate_events(sales_events, keys=("sku", "product_id"))
        restock_counter = self._aggregate_events(restock_events or [], keys=("sku", "product_id"))

        per_sku: Dict[str, Dict[str, object]] = {}
        totals = {
            "expected_value": 0.0,
            "actual_value": 0.0,
            "shrinkage_value": 0.0,
            "shrinkage_units": 0,
        }
        alerts: List[Dict[str, object]] = []

        all_skus = set(baseline_inventory) | set(actual_inventory) | set(sales_counter)

        for sku in sorted(all_skus):
            baseline = baseline_inventory.get(sku, 0)
            actual = actual_inventory.get(sku, 0)
            sales = sales_counter.get(sku, 0)
            restocks = restock_counter.get(sku, 0)
            expected_after_sales = max(baseline - sales + restocks, 0)
            delta = expected_after_sales - actual

            price = catalog.get(sku, {}).get("price", 0.0)
            name = catalog.get(sku, {}).get("name", sku)

            expected_value = expected_after_sales * price
            actual_value = actual * price

            totals["expected_value"] += expected_value
            totals["actual_value"] += actual_value

            per_sku[sku] = {
                "product_name": name,
                "expected_after_sales": expected_after_sales,
                "actual": actual,
                "delta_units": delta,
                "unit_price": price,
                "delta_value": round(delta * price, 2),
                "sales_count": sales,
                "restock_count": restocks,
            }

            if delta > 0:
                totals["shrinkage_units"] += delta
                totals["shrinkage_value"] += delta * price

                alert_priority = "high" if (delta * price) >= self.high_value_threshold else "medium"
                alerts.append(
                    {
                        "event_type": "inventory_shrinkage_alert",
                        "sku": sku,
                        "product_name": name,
                        "shrinkage_units": delta,
                        "shrinkage_value": round(delta * price, 2),
                        "priority": alert_priority,
                    }
                )

        totals["expected_value"] = round(totals["expected_value"], 2)
        totals["actual_value"] = round(totals["actual_value"], 2)
        totals["shrinkage_value"] = round(totals["shrinkage_value"], 2)

        return {"per_sku": per_sku, "totals": totals, "alerts": alerts}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _aggregate_events(self, events: Iterable[Dict[str, object]], keys: Tuple[str, ...]) -> Counter:
        counter: Counter = Counter()
        for event in events or []:
            sku = self._first_present(event, keys)
            if sku:
                counter[str(sku)] += int(event.get("quantity", 1))
        return counter

    def _first_present(self, event: Dict[str, object], keys: Tuple[str, ...]) -> Optional[str]:
        for key in keys:
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        data = event.get("data")
        if isinstance(data, dict):
            for key in keys:
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    def _high_value_watch(
        self,
        actual_inventory: Dict[str, int],
        catalog: Dict[str, Dict[str, object]],
    ) -> List[Dict[str, object]]:
        watch_list: List[Dict[str, object]] = []
        for sku, price_info in catalog.items():
            price = price_info.get("price", 0.0)
            if price < self.high_value_threshold:
                continue
            on_hand = actual_inventory.get(sku, 0)
            if on_hand <= 2:
                watch_list.append(
                    {
                        "sku": sku,
                        "product_name": price_info.get("name", sku),
                        "units_on_hand": on_hand,
                        "unit_price": price,
                        "message": "Replenish high-value item",
                    }
                )
        return watch_list

    def _load_catalog(self) -> Dict[str, Dict[str, object]]:
        if self._catalog is not None:
            return self._catalog

        catalog_path = self._data_root / "products_list.csv"
        catalog: Dict[str, Dict[str, object]] = {}

        if catalog_path.exists():
            with catalog_path.open("r", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    sku = row.get("SKU") or row.get("sku")
                    if not sku:
                        continue
                    try:
                        price = float(row.get("price", 0) or 0)
                    except ValueError:
                        price = 0.0
                    catalog[sku] = {
                        "name": row.get("product_name", sku),
                        "price": price,
                        "weight": row.get("weight"),
                        "barcode": row.get("barcode"),
                    }

        self._catalog = catalog
        return catalog


inventory_analyzer = InventoryAnalyzer()