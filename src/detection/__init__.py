"""Detection package public API."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from .barcode_switching import detect_barcode_switching, reset_state as reset_barcode
from .scanner_avoidance import detect_scanner_avoidance, reset_state as reset_scanner
from .weight_discrepancy import detect_weight_discrepancy, reset_state as reset_weight

if TYPE_CHECKING:  # pragma: no cover - type-checking aid only
	from ..pipeline.transform import SentinelEvent

DETECTOR_FUNCS = (
	detect_barcode_switching,
	detect_scanner_avoidance,
	detect_weight_discrepancy,
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


__all__ = ["process_event", "reset_all"]
