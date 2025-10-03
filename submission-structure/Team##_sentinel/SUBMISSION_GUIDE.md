# Submission Guide

Complete this template before zipping your submission. Keep the file at the
project root.

## Team details
- Team name: <ENTER INFO>
- Members: <ENTER INFO>
- Primary contact email: <ENTER INFO>

## Judge run command
Judges will `cd evidence/executables/` and run **one command** on Ubuntu 24.04:

```
python3 run_demo.py <ENTER PARAMETERS IF NEEDED>
```

Adapt `run_demo.py` to set up dependencies, start any services, ingest data,
and write all artefacts into `./results/` (relative to `evidence/executables/`).
No additional scripts or manual steps are allowed.

## Checklist before zipping and submitting
- Algorithms tagged with `# @algorithm Name | Purpose` comments: <ENTER INFO>
- Evidence artefacts present in `evidence/`: <ENTER INFO>
- Source code complete under `src/`: <ENTER INFO>
