# Dilusha — Streaming & Infra

Focus: make data flow reliable and easy to consume.

## Scope
- Own `streaming-server/stream_server.py`: flags, speed, dataset selection, loop stability.
- Improve `streaming-clients/` (Python/Node/Java): CLI args, reconnection, sample parsing.
- Provide `src/io/stream_reader.py` (planned) to yield normalized messages.
- Create `scripts/dev_start.ps1` for Windows quickstart.
- Document ports and topology in `HACKATHON_PLAN.md` cross-links.

## Deliverables
- Robust server defaults; README snippets for Windows.
- A small Python library function: `read_stream(host, port) -> Iterator[dict]`.
- Smoke tests: connect, read N events, validate keys.

## Milestones
- M1: Server runs at 10× with loop; banner correct.
- M2: Python client exposes `--limit`, timeouts.
- M3: `read_stream` published under `src/io` with docstring.
