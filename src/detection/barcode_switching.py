"""Barcode switching detector.

The logic fuses high-confidence computer-vision predictions with POS scans. If
the vision system predicts a different SKU than the barcode that was scanned
within a small time window, we emit a suspicious-event record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..pipeline.transform import SentinelEvent

# Aliases used by the simulator / datasets
POS_DATASETS = {"POS_Transactions", "pos_transactions"}
VISION_DATASETS = {"Product_recognism", "product_recognition"}

VISION_CONFIDENCE_THRESHOLD = 0.65
PREDICTION_TTL = timedelta(seconds=20)


@dataclass(slots=True)
class VisionPrediction:
    sku: str
    accuracy: float
    timestamp: datetime


_latest_predictions: Dict[str, VisionPrediction] = {}


def reset_state() -> None:
    """Reset cached predictions (useful for unit tests)."""

    _latest_predictions.clear()


def detect_barcode_switching(event: SentinelEvent) -> List[dict]:
    """Process an event and return zero or more anomaly records."""

    station_id = event.station_id
    if not station_id:
        return []

    now = event.timestamp

    if event.dataset in VISION_DATASETS:
        vision_payload = event.payload.get("data", {})
        sku = vision_payload.get("predicted_product")
        accuracy = vision_payload.get("accuracy")
        if isinstance(sku, str) and isinstance(accuracy, (int, float)):
            if accuracy >= VISION_CONFIDENCE_THRESHOLD:
                _latest_predictions[station_id] = VisionPrediction(sku=sku, accuracy=float(accuracy), timestamp=now)
        return []

    # Expire stale predictions before evaluating POS events
    _expire_predictions(now)

    if event.dataset not in POS_DATASETS:
        return []

    pos_data = event.payload.get("data", {})
    scanned_sku = pos_data.get("sku")
    if not isinstance(scanned_sku, str):
        return []

    vision_prediction: Optional[VisionPrediction] = _latest_predictions.get(station_id)
    if not vision_prediction:
        return []

    # Only flag mismatches
    if _items_match(vision_prediction.sku, scanned_sku):
        _latest_predictions.pop(station_id, None)
        return []

    event_details = {
        "type": "barcode_switching",
        "station_id": station_id,
        "timestamp": now.isoformat(timespec="milliseconds"),
        "confidence": round(min(0.99, vision_prediction.accuracy), 2),
        "evidence": {
            "predicted_product": vision_prediction.sku,
            "predicted_accuracy": vision_prediction.accuracy,
            "scanned_sku": scanned_sku,
            "product_name": pos_data.get("product_name"),
        },
    }

    # Clear the cached prediction to avoid duplicate alerts.
    _latest_predictions.pop(station_id, None)
    return [event_details]


def _expire_predictions(reference_time: datetime) -> None:
    expired = [station for station, pred in _latest_predictions.items() if reference_time - pred.timestamp > PREDICTION_TTL]
    for station in expired:
        _latest_predictions.pop(station, None)


def _items_match(predicted_sku: str, scanned_sku: str) -> bool:
    # Allow loose comparison ignoring case and common prefixes.
    return predicted_sku.strip().upper() == scanned_sku.strip().upper()
