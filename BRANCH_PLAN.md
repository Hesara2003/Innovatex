# Branch plan

## Hesara branch (`hesara`)

**Focus:** Detection algorithms, analytics, and submission artefacts.

### Key objectives
- Implement anomaly detectors (barcode switching, scanner avoidance, weight discrepancy, system health, queue health, inventory discrepancy).
- Maintain the shared Sentinel event schema with confidence metrics and attributes.
- Provide analytics modules for queue KPIs, staffing forecasts, kiosk allocation, and operational insights.
- Ensure automated coverage: detector unit tests, analytics regression tests, integration run of `run_demo.py`.
- Produce competition-ready artefacts under `submission-structure/Team##_sentinel/evidence`.

### Current status
- Detector suite ported and extended; registry exposes reset hooks for tests.
- Analytics service (`queue_metrics.py`) now merges Sandali's real-time tooling with batch KPI computation.
- Operational insight generator wired into the demo runner; integration test (`tests/test_integration_runner.py`) validates the end-to-end flow.
- All pytest suites (18 tests) passing; demo runner verified against simulator streams.

### Next actions
- Keep `docs/workstreams/hesara.md` aligned with upcoming detector or analytics changes.
- Re-run `run_demo.py` after meaningful pipeline updates to refresh evidence artefacts.
- Coordinate with frontend/dashboard owners for data contract validation if visualizations are added.

---

## Dilusha branch (`dilusha`)

**Focus:** Streaming infrastructure, simulator hardening, and developer tooling.

### Key objectives
- Stabilize `streaming-server/stream_server.py` defaults and health checks.
- Improve sample clients located in `streaming-clients/` (Node, Python, Java).
- Provide reusable stream-reader utilities under `src/io/` for cross-team consumption.
- Supply development scripts (for example `scripts/dev_start.ps1`) to simplify local bring-up of server and clients.

### Current status & follow-ups
- See `docs/workstreams/dilusha.md` for detailed progress and outstanding tasks.
- Align simulator payloads with the Sentinel event schema to guarantee compatibility with the detection pipeline.
- Ensure monitoring/logging hooks surface queue and system health signals for operational dashboards.

