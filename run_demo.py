#!/usr/bin/env python3
"""Deterministic demo runner for the InnovateX Project Sentinel pipeline."""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from src.analytics import evaluate
from src.detection import (
    barcode_switching,
    inventory_discrepancy,
    queue_health,
    reset_all,
    scanner_avoidance,
    system_health,
    weight_discrepancy,
)
from src.pipeline import joiners, transform


def _configure_determinism(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)


def _ensure_results_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _dataset_counts(records: Iterable[dict]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for record in records:
        dataset = record.get("dataset", "unknown")
        counter[dataset] += 1
    return counter


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the offline normalization/enrichment demo")
    parser.add_argument("--data-root", type=Path, default=Path("data/input"), help="Directory with JSONL datasets")
    parser.add_argument("--products-csv", type=Path, default=None, help="Path to products_list.csv (defaults to data-root)")
    parser.add_argument("--customers-csv", type=Path, default=None, help="Path to customer_data.csv (defaults to data-root)")
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=None,
        help="Subset of datasets to load (default: canonical set)",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional cap on emitted events")
    parser.add_argument("--results-dir", type=Path, default=Path("results"), help="Output directory for JSONL artefacts")
    parser.add_argument("--seed", type=int, default=42, help="Seed used for deterministic behaviour")
    parser.add_argument("--reference", type=Path, default=None, help="Optional reference events JSONL for evaluation")
    parser.add_argument(
        "--eval-fields",
        nargs="+",
        default=None,
        help="Fields (dot-notation) used when computing precision/recall",
    )
    parser.add_argument("--keep-missing", action="store_true", help="Keep events with missing eval fields")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging verbosity",
    )
    return parser


def _run_detectors(events: Iterable[transform.SentinelEvent]) -> List[dict]:
    """Run all registered detectors and return a flat list of alerts."""
    reset_all()
    alerts: List[dict] = []
    detector_map = {
        "barcode_switching": barcode_switching.detect_barcode_switching,
        "inventory_discrepancy": inventory_discrepancy.detect_inventory_discrepancy,
        "queue_health": queue_health.detect_queue_health,
        "scanner_avoidance": scanner_avoidance.detect_scanner_avoidance,
        "system_health": system_health.detect_system_health,
        "weight_discrepancy": weight_discrepancy.detect_weight_discrepancy,
    }

    for event in events:
        for name, detector_func in detector_map.items():
            try:
                new_alerts = detector_func(event)
                if new_alerts:
                    alerts.extend(new_alerts)
            except Exception:
                logging.warning("Detector %s failed on event: %s", name, event, exc_info=True)
    return alerts


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(levelname)s %(message)s")

    _configure_determinism(args.seed)

    data_root = args.data_root
    if not data_root.exists():
        raise SystemExit(f"Data root not found: {data_root}")

    datasets = args.datasets if args.datasets else None

    logging.info("Loading datasets from %s", data_root)
    records = transform.load_datasets(data_root, datasets=datasets)
    records.sort(key=lambda rec: rec.timestamp)

    if args.limit is not None:
        records = records[: args.limit]

    products_path = args.products_csv or data_root / "products_list.csv"
    customers_path = args.customers_csv or data_root / "customer_data.csv"

    products = joiners.load_product_catalog(products_path, strict=False)
    customers = joiners.load_customer_directory(customers_path, strict=False)

    enriched_list: List[dict] = list(joiners.enrich_events(records, products=products, customers=customers))

    results_dir = _ensure_results_dir(args.results_dir)
    out_path = results_dir / "events.jsonl"
    _write_jsonl(out_path, enriched_list)
    logging.info("Wrote %d events to %s", len(enriched_list), out_path)

    logging.info("Running all detectors on %d enriched events", len(records))
    alerts = _run_detectors(records)
    alerts_path = results_dir / "alerts.jsonl"
    _write_jsonl(alerts_path, alerts)
    logging.info("Wrote %d alerts to %s", len(alerts), alerts_path)

    counts = _dataset_counts(enriched_list)
    for dataset, count in counts.items():
        logging.info("dataset=%s count=%d", dataset, count)

    if args.reference:
        eval_fields = args.eval_fields if args.eval_fields else ["dataset", "sku"]
        logging.info("Evaluating against %s using fields %s", args.reference, eval_fields)
        result = evaluate.evaluate_files(out_path, args.reference, eval_fields, drop_missing=not args.keep_missing)
        logging.info(
            "precision=%.3f recall=%.3f f1=%.3f support=%d",
            result.precision,
            result.recall,
            result.f1,
            result.support,
        )
        if result.false_positives:
            logging.debug("False positives: %s", result.false_positives)
        if result.false_negatives:
            logging.debug("False negatives: %s", result.false_negatives)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
