#!/usr/bin/env python3
"""
Judge entrypoint: single command automation.

Responsibilities:
- Ensure output directory exists at ./results/
- Optionally start local simulator (if not already running)
- Read a small number of events from the TCP stream to validate plumbing
- Write a minimal ./results/events.jsonl artefact

Notes:
- Keep this script dependency-light (standard library only) for portability.
- Real competition runs should replace the sampling with full pipeline.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# Make the project root importable so we can leverage the src/ package.
REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.analytics.operations import generate_insights
from src.detection import process_event as run_detectors
from src.detection import reset_all as reset_detectors
from src.pipeline.transform import SentinelEvent, normalize_event


def ensure_results_dir(base: Path) -> Path:
    results = base / "results"
    results.mkdir(parents=True, exist_ok=True)
    return results


def maybe_start_simulator(host: str, port: int) -> subprocess.Popen | None:
    """Attempt to start the local simulator if the port is not accepting connections."""
    if _is_port_open(host, port):
        return None
    # Try launching the simulator from repo path if found
    sim_py = REPO_ROOT / "streaming-server" / "stream_server.py"
    if not sim_py.exists():
        # In some layouts, simulator may live under data/streaming-server
        alt = REPO_ROOT / "data" / "streaming-server" / "stream_server.py"
        if alt.exists():
            sim_py = alt
        else:
            print(f"[warn] Simulator not found at {sim_py} or {alt}; continuing without starting it.")
            return None
    print(f"[info] Starting simulator: {sim_py}")
    # Use a moderate speed and loop for a short demo
    # Start detached so we can proceed to connect
    return subprocess.Popen([sys.executable, str(sim_py), "--port", str(port), "--speed", "10", "--loop"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@contextmanager
def _stream_connection(host: str, port: int, timeout: float = 1.0):
    """Context manager that yields an open socket connection."""

    conn = socket.create_connection((host, port), timeout=timeout)
    try:
        yield conn
    finally:
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        conn.close()


def stream_frames(host: str, port: int, limit: int, timeout: float = 15.0):
    """Yield newline-delimited JSON frames from the TCP stream."""

    deadline = time.time() + timeout
    received = 0
    backoff = 0.3

    while received < limit and time.time() < deadline:
        try:
            with _stream_connection(host, port) as conn:
                conn.settimeout(1.5)
                buf = b""
                while received < limit and time.time() < deadline:
                    try:
                        chunk = conn.recv(4096)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf and received < limit:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        received += 1
                        yield line.decode("utf-8", errors="ignore")
                if received >= limit:
                    return
        except OSError:
            time.sleep(backoff)
            backoff = min(backoff * 1.5, 1.5)
    return


def run_pipeline(host: str, port: int, limit: int, out_path: Path) -> tuple[int, list[dict], list[SentinelEvent]]:
    """Stream frames, run detectors, and return aggregate results."""

    raw_log_path = out_path.with_name("raw_stream.jsonl")
    detections: list[dict] = []
    events: list[SentinelEvent] = []
    frames = 0

    with raw_log_path.open("w", encoding="utf-8") as raw_file:
        for line in stream_frames(host, port, limit):
            frames += 1
            raw_file.write(line + "\n")
            normalized = normalize_event(line.encode("utf-8"))
            if normalized is None:
                continue
            events.append(normalized)
            alerts = run_detectors(normalized)
            for alert in alerts:
                enriched = dict(alert)
                enriched.setdefault("source", {})
                enriched["source"].update(
                    {
                        "dataset": normalized.dataset,
                        "sequence": normalized.sequence,
                        "event_timestamp": normalized.timestamp.isoformat(timespec="milliseconds"),
                    }
                )
                detections.append(enriched)

    with out_path.open("w", encoding="utf-8") as det_file:
        if detections:
            for record in detections:
                det_file.write(json.dumps(record) + "\n")
        else:
            det_file.write(json.dumps({"info": "no_detections", "frames": frames}) + "\n")

    return frames, detections, events


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Project Sentinel demo runner")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--limit", type=int, default=200, help="sample N stream frames before stopping")
    parser.add_argument("--no-start-sim", action="store_true", help="do not attempt to start local simulator")
    args = parser.parse_args(argv)

    base = Path(__file__).parent
    results_dir = ensure_results_dir(base)

    proc = None
    try:
        if not args.no_start_sim:
            proc = maybe_start_simulator(args.host, args.port)
            # Give the simulator a moment to bind
            time.sleep(0.5)

        reset_detectors()

        out_path = results_dir / "events.jsonl"
        frames, detections, events = run_pipeline(args.host, args.port, args.limit, out_path)

        if frames == 0:
            print("[error] No events received from stream; exiting with failure.")
            return 2

        insights = generate_insights(events, detections)
        insights_path = results_dir / "insights.json"
        with insights_path.open("w", encoding="utf-8") as handle:
            json.dump(insights, handle, indent=2)

        print(
            f"[info] Processed {frames} frames, emitted {len(detections)} detections -> {out_path}"
        )
        return 0
    finally:
        if proc is not None:
            # Best-effort cleanup; simulator is also fine to keep running in some judging setups
            try:
                proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
