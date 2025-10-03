# Team branches and responsibilities

Branches created for each member. Use these as your long-lived feature branches and open PRs to `main`.

- `dilusha` — Streaming server, client tooling, and infra glue
- `hesara` — Event detection algorithms (barcode switching, scanner avoidance, weight discrepancy)
- `sandil` — Data engineering, schema alignment, and evaluation pipeline
- `sandali` — Customer experience analytics, dashboards, and demo packaging

## Workflow
1. Branch naming: use your branch for all work; short-lived task branches can be `name/task-slug`.
2. Commits: small, focused; reference `# @algorithm` tags where relevant.
3. PRs: open to `main`; request at least 1 review from a different member.
4. CI (optional): add lint/tests later; keep `run_demo.py` green.

## Shared anchors
- Simulator: `streaming-server/stream_server.py`
- Clients: `streaming-clients/`
- Data: `data/input/`, reference events: `data/output/events.jsonl`
- Submission: `submission-structure/Team##_sentinel/`
- Hackathon plan: `HACKATHON_PLAN.md`
