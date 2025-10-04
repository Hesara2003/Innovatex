# Hesara — Detection & Insights

Focus: deliver the full detection suite, shared analytics, and competition-ready artifacts (`events.jsonl`, `insights.json`).

## Scope
- Maintain Sentinel event schema (type, timestamp, confidence, attributes) shared across detectors and analytics.
- Implement and iterate on detectors for:
  - Barcode switching
  - Scanner avoidance
  - Weight discrepancy
  - System health / scanner outages
  - Queue congestion & prolonged wait times
  - Inventory count discrepancies
- Provide detector registry and reset hooks covering all modules in `src/detection/`.
- Build analytics for queue KPIs and operational recommendations (`src/analytics/queue_metrics.py`, `src/analytics/operations.py`).
- Integrate demo runner to stream data, execute detectors/analytics, and persist outputs under `submission-structure/Team##_sentinel/evidence`.
- Backfill unit tests across detectors and analytics; smoke-test demo pipeline.

## Deliverables
- `src/detection/barcode_switching.py`
- `src/detection/scanner_avoidance.py`
- `src/detection/weight_discrepancy.py`
- `src/detection/system_health.py`
- `src/detection/queue_health.py`
- `src/detection/inventory_discrepancy.py`
- `src/detection/__init__.py` (registry & reset wiring)
- `src/analytics/queue_metrics.py`
- `src/analytics/operations.py`
- `submission-structure/Team##_sentinel/evidence/executables/run_demo.py`
- `submission-structure/Team##_sentinel/evidence/output/*` example artifacts (`events.jsonl`, `insights.json`)
- `tests/test_detection_*.py`, `tests/test_analytics_*.py`

## Milestones
- M1: Sentinel event schema finalized; base detectors emit validated events.
- M2: Extended detectors (system, queue, inventory) and analytics produce actionable signals on sample streams.
- M3: Demo runner writes consolidated detections & insights; confidence calibration, deduping window, and automated tests locked in.
