# InnovateX Hackathon — Project Sentinel

This plan translates the repository assets into a ready-to-run hackathon. It covers goals, tracks, logistics, infra, judging, and submission standards. All paths below refer to this repo’s structure.

## 1) Theme and Outcomes
- Theme: Retail loss prevention and checkout experience using multi-source streaming data (RFID, POS, computer vision, queue metrics).
- Expected outcomes:
  - Event detection: shrink/theft signals, barcode switching, scanner avoidance, weight discrepancy, queue anomalies.
  - Experience insights: self-checkout friction, misplacements, and dwell-time hot spots.
  - A single consolidated events.json[l] output for given datasets, plus a 2-minute demo script.

## 2) Challenge Packs
Use the attached brief in `project-sentinel.pdf` and examples in `resources/`.

- Data simulation: `streaming-server/` + `streaming-clients/` replay combined inputs from `data/input/`.
- Reference schema: `data/output/events.jsonl` illustrates event types/shape (example only; not derived from input).
- Videos (optional, for storytelling): `resources/videos/*` contain scenarios (e.g., Shoplifting, SelfCheckout anomalies).

## 3) Tracks
- Track A — Real-time Event Detection
  - Detect and emit events for theft, misplacement, barcode switching, scanner avoidance, weight discrepancies, and suspicious RFID movements.
- Track B — Customer Experience & Ops
  - Quantify queue states, dwell time, and friction points; propose actionable recommendations.
- Track C — Data Engineering & Tooling (optional)
  - Build robust stream ingestion, feature pipelines, and reproducible evaluation scripts.

Teams may submit to multiple tracks with one consolidated demo.

## 4) Schedule (1-day format; adapt as needed)
- 09:00 Kickoff + challenge brief (20m)
- 09:20 Tech quickstart (20m): repo tour, how to run server/clients, submission rules
- 09:40 Team formation + ideation (20m)
- 10:00 Build sprint I
- 12:30 Lunch break (30m)
- 13:00 Build sprint II
- 16:30 Code freeze; run on Test set
- 17:00 Final dataset drop (10m before close in some formats)
- 17:10 Final runs + packaging
- 17:40 Demos (2 minutes/team)
- 18:30 Awards + wrap

For 2-day events: add checkpoints, office hours, and an extended demo block.

## 5) Infrastructure
- Local-first, no external dependencies required.
- Python 3.9+ for simulator and sample client; Node.js and Java clients optional.
- OS: Windows/macOS/Linux; Judges will run on Ubuntu 24.04 per `SUBMISSION_GUIDE.md`.

### Streaming server
- Location: `streaming-server/stream_server.py` (from repo root). Note: Some docs reference `data/streaming-server`—use the actual path in this workspace.
- Typical run (Windows PowerShell):
  ```powershell
  cd streaming-server
  python .\stream_server.py --port 8765 --speed 10 --loop
  ```
- Clients (optional):
  ```powershell
  cd streaming-clients
  python .\client_example.py --host 127.0.0.1 --port 8765 --limit 5
  node .\client_example_node.js --host 127.0.0.1 --port 8765 --limit 5
  javac .\ClientExample.java; java ClientExample --host 127.0.0.1 --port 8765 --limit 5
  ```

### Datasets
- Initial: `data/input/` for practice
- Test: provided during event
- Final: provided near deadline

Teams generate and deliver:
- `evidence/output/test/events.json` (or .jsonl)
- `evidence/output/final/events.json` (or .jsonl)

## 6) Event Specification
- Emit newline-delimited JSON objects.
- Each event should include at minimum: `event_type`, `timestamp`, `source`, `confidence` (0–1), and an `attributes` object with fields relevant to the detector (e.g., `sku`, `station_id`, `epc`, `delta_weight_g`).
- The example `data/output/events.jsonl` shows the taxonomy and structure to mirror.

## 7) Judging Rubric (100 points)
- Detection accuracy & coverage (35)
- Signal quality (precision of metadata, confidence calibration) (15)
- Reproducibility (single-command run, deterministic outputs) (15)
- Engineering & robustness (error handling, edge cases, performance) (15)
- Demo clarity (storytelling in 2 minutes, links to evidence) (10)
- Insightfulness (ops/customer experience takeaways) (10)

Tie-breakers: adherence to submission template, clear algorithm tags, and quality of evidence artifacts.

## 8) Submission Rules
Follow `submission-structure/Team##_sentinel/SUBMISSION_GUIDE.md` and keep the template at repo root.

- Judges will run exactly:
  ```bash
  cd evidence/executables/
  python3 run_demo.py
  ```
- Your `run_demo.py` must:
  - Install dependencies if needed
  - Start services (e.g., simulator) if required
  - Ingest the correct dataset (Test or Final)
  - Generate outputs under `./results/` (relative to `evidence/executables/`)
  - Exit successfully with no manual steps
- Annotate algorithms with `# @algorithm Name | Purpose` in source.

Packaging: Zip the repository with `submission-structure/Team##_sentinel/` completed and evidence populated.

## 9) Guidance and Edge Cases
- Handle missing or delayed records gracefully (e.g., late RFID vs POS timing).
- Time alignment: use server-adjusted timestamps; document any resampling.
- Schema drift: if a field is absent, default safely and log once.
- Performance: aim for at least 10× replay speed; batch I/O for JSONL writes.
- Determinism: seeded randomness only; ensure repeated runs produce identical files.

## 10) Optional Extras
- Unit tests for event mappers and detectors.
- A lightweight `src/` with modular detectors per event type.
- A small `README` in `evidence/executables/` describing expected runtime and outputs.

## 11) Quickstart for Participants (Windows PowerShell)
```powershell
# 1) Explore data and run the stream
python --version
cd streaming-server
python .\stream_server.py --port 8765 --speed 10 --loop

# 2) Consume with sample client (optional)
cd ..\streaming-clients
python .\client_example.py --host 127.0.0.1 --port 8765 --limit 5

# 3) Implement detectors and produce events.jsonl
#    Write your pipeline to read the stream and emit JSONL events to evidence/output/*
```

## 12) Organizer Checklist
- [ ] Verify `stream_server.py` path and ports on lab machines
- [ ] Print `project-sentinel.pdf` highlights and rubric
- [ ] Prepare Test and Final datasets delivery method (Drive/USB)
- [ ] Confirm demo timing system and projector
- [ ] Provide zip naming convention and hand-in location

— End of plan —
