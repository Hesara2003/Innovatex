"""Lookup and enrichment helpers for Project Sentinel datasets."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, Iterator, Mapping, Optional

from .transform import NormalizedRecord


Catalog = Dict[str, Dict[str, object]]


def _coerce(value: str) -> object:
    """Attempt to convert CSV fields to native Python types."""

    text = value.strip()
    if text == "":
        return ""
    for cast in (int, float):
        try:
            converted = cast(text)
        except ValueError:
            continue
        else:
            # Preserve integers (e.g. quantities) where possible.
            return converted
    return text


def _read_catalog(path: Path, key_field: str, *, strict: bool) -> Catalog:
    if not path.exists():
        if strict:
            raise FileNotFoundError(path)
        return {}

    catalog: Catalog = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = row.get(key_field)
            if not key:
                continue
            catalog[key] = {k: _coerce(v) for k, v in row.items() if k}
    return catalog


def load_product_catalog(path: Path, *, strict: bool = True) -> Catalog:
    """Load `products_list.csv` keyed by SKU."""

    return _read_catalog(path, key_field="SKU", strict=strict)


def load_customer_directory(path: Path, *, strict: bool = True) -> Catalog:
    """Load `customer_data.csv` keyed by Customer_ID."""

    return _read_catalog(path, key_field="Customer_ID", strict=strict)


def enrich_event(
    record: NormalizedRecord,
    *,
    products: Optional[Mapping[str, Mapping[str, object]]] = None,
    customers: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Dict[str, object]:
    """Return an enriched dictionary for a ``NormalizedRecord``."""

    event = record.to_dict()
    enrichments: Dict[str, object] = {}

    if products is not None and record.sku:
        product = products.get(record.sku)
        if product:
            enrichments["product"] = dict(product)

    if customers is not None and record.customer_id:
        customer = customers.get(record.customer_id)
        if customer:
            enrichments["customer"] = dict(customer)

    if record.metadata:
        enrichments.setdefault("metadata", dict(record.metadata))

    if enrichments:
        event["enrichment"] = enrichments

    return event


def enrich_events(
    records: Iterable[NormalizedRecord],
    *,
    products: Optional[Mapping[str, Mapping[str, object]]] = None,
    customers: Optional[Mapping[str, Mapping[str, object]]] = None,
) -> Iterator[Dict[str, object]]:
    """Yield enriched dictionaries for a sequence of records."""

    for record in records:
        yield enrich_event(record, products=products, customers=customers)


__all__ = [
    "Catalog",
    "enrich_event",
    "enrich_events",
    "load_customer_directory",
    "load_product_catalog",
]
