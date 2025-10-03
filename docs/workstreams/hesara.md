# Hesara — Detection Algorithms

Focus: implement core detectors and emit events.jsonl.

## Scope
- Implement detectors for:
  - Barcode switching
  - Scanner avoidance
  - Weight discrepancy
- Define shared event schema (type, timestamp, confidence, attributes).
- Add `src/detection/` with per-detector modules and `__init__.py`.
- Unit tests for each detector’s core logic.

## Deliverables
- `src/detection/barcode_switching.py`
- `src/detection/scanner_avoidance.py`
- `src/detection/weight_discrepancy.py`
- `tests/test_detection_*.py`
- `evidence/output/test/events.jsonl` example run

## Milestones
- M1: Event schema finalized; example events pass validation.
- M2: Three detectors produce signals from sample stream.
- M3: Confidence calibration and deduping window.
