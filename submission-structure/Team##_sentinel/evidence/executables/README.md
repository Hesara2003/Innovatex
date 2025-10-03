# Evidence executables

Judges will run exactly from this folder on Ubuntu 24.04:

```
python3 run_demo.py
```

What this script does now:
- Creates `./results/` if missing
- Attempts to start the local simulator if not running
- Connects to the TCP stream on 127.0.0.1:8765
- Reads a small sample of events and writes them to `./results/events.jsonl`

Flags (optional):
```
python3 run_demo.py --host 127.0.0.1 --port 8765 --limit 10 --no-start-sim
```

Replace the sampling logic with your full pipeline as you implement detectors, transforms, and evaluation.
