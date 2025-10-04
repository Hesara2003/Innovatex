"""Operational insight generation based on detections and live metrics."""

from __future__ import annotations

from math import ceil
from typing import Dict, Iterable, List

from ..detection import queue_health
from ..pipeline.transform import SentinelEvent
from .queue_metrics import QUEUE_DATASETS, compute_kpis

TARGET_CUSTOMERS_PER_ASSOCIATE_PER_HOUR = 45
TARGET_CUSTOMERS_PER_KIOSK = 6


def generate_insights(events: Iterable[SentinelEvent], detections: List[dict]) -> dict:
    queue_events = [event for event in events if event.dataset in QUEUE_DATASETS]
    kpis = compute_kpis(queue_events)

    staffing = _forecast_staffing(kpis)
    kiosk_plan = _recommend_kiosk_allocation(kpis)
    additional = _derive_additional_insights(kpis, detections)

    return {
        "kpis": kpis,
        "staffing": staffing,
        "kiosk_plan": kiosk_plan,
        "additional_insights": additional,
    }


def _forecast_staffing(kpis: dict) -> dict:
    arrival_rate = kpis.get("avg_arrival_rate_per_min")
    avg_wait = kpis.get("avg_wait_seconds")
    if arrival_rate is None or avg_wait is None or avg_wait <= 0:
        return {
            "recommended_associates": None,
            "basis": "Insufficient queue data to forecast staffing.",
        }

    customers_per_hour = arrival_rate * 60
    associates_needed = max(1, ceil(customers_per_hour / TARGET_CUSTOMERS_PER_ASSOCIATE_PER_HOUR))

    return {
        "recommended_associates": associates_needed,
        "basis": f"Average arrival rate {arrival_rate:.2f} customers/min with wait {avg_wait:.0f}s.",
    }


def _recommend_kiosk_allocation(kpis: dict) -> dict:
    avg_queue = kpis.get("avg_queue_length")
    peak_queue = kpis.get("peak_queue_length")
    if avg_queue is None:
        return {
            "recommended_kiosks": None,
            "basis": "No queue length data available.",
        }

    recommended = max(1, ceil(max(avg_queue, peak_queue or 0) / TARGET_CUSTOMERS_PER_KIOSK))
    return {
        "recommended_kiosks": recommended,
        "basis": f"Maintain ~{TARGET_CUSTOMERS_PER_KIOSK} customers per kiosk; avg queue {avg_queue:.1f} (peak {peak_queue}).",
    }


def _derive_additional_insights(kpis: dict, detections: List[dict]) -> List[str]:
    insights: List[str] = []

    if kpis.get("avg_wait_seconds") and kpis["avg_wait_seconds"] > queue_health.MAX_WAIT_SECONDS:
        insights.append(
            "Extend associate coverage at self-checkout during peak windows to cut dwell times below two minutes."
        )

    if any(det["type"] == "system_error" for det in detections):
        insights.append("Schedule preventive maintenance for scanners reporting frequent errors.")

    inventory_flags = [det for det in detections if det["type"] == "inventory_discrepancy"]
    if inventory_flags:
        top = inventory_flags[0]
        insights.append(
            f"Inventory mismatch detected for SKU {top['evidence']['sku']}; investigate shrink and reconcile counts."
        )

    if not insights:
        insights.append("Operations running within targets. Continue monitoring real-time dashboards for anomalies.")

    return insights
