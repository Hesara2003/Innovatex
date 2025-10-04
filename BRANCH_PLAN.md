<
# Branch plan — Hesara# Branch plan — Dilusha



Branch: `hesara`Branch: `dilusha`



Primary focus: detection algorithms and event emission.Primary focus: streaming server, client tooling, and infra glue.





- Implement detectors: barcode switching, scanner avoidance, weight discrepancy.- Stabilize `streaming-server/stream_server.py` and default flags.

- Define event schema with confidence and attributes.- Improve sample clients (`streaming-clients/*`).

- Add tests under `tests/` covering happy path and edge cases.- Create `src/io/stream_reader.py` to normalize messages.

- Produce `evidence/output/test/events.jsonl` from sample run.- Provide `scripts/dev_start.ps1` to launch server/clients easily.



See also: `docs/workstreams/hesara.md`.See also: `docs/workstreams/dilusha.md`.

