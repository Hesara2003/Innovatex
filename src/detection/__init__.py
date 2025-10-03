"""Detection package public API."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from .barcode_switching import detect_barcode_switching, reset_state as reset_barcode
from .queue_health import detect_queue_health, reset_state as reset_queue
from .scanner_avoidance import detect_scanner_avoidance, reset_state as reset_scanner
from .system_health import detect_system_health, reset_state as reset_system
from .weight_discrepancy import detect_weight_discrepancy, reset_state as reset_weight
from .inventory_discrepancy import detect_inventory_discrepancy, reset_state as reset_inventory

if TYPE_CHECKING:  # pragma: no cover - type-checking aid only
	from ..pipeline.transform import SentinelEvent

DETECTOR_FUNCS = (
	detect_barcode_switching,
	detect_scanner_avoidance,
	detect_weight_discrepancy,
	detect_system_health,
	detect_queue_health,
	detect_inventory_discrepancy,
)


def process_event(event: "SentinelEvent") -> List[dict]:
	"""Run the configured detectors and return all alerts produced."""

	alerts: List[dict] = []
	for detector in DETECTOR_FUNCS:
		alerts.extend(detector(event))
	return alerts


def reset_all() -> None:
	"""Reset stateful detectors (primarily for tests)."""

	reset_barcode()
	reset_scanner()
	reset_weight()
	reset_system()
	reset_queue()
	reset_inventory()


__all__ = ["process_event", "reset_all"]
