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
import os
import socket
import subprocess
import sys
import time
from pathlib import Path


def ensure_results_dir(base: Path) -> Path:
    results = base / "results"
    results.mkdir(parents=True, exist_ok=True)
    return results


def maybe_start_simulator(host: str, port: int) -> subprocess.Popen | None:
    """Attempt to start the local simulator if the port is not accepting connections."""
    if _is_port_open(host, port):
        return None
    # Try launching the simulator from repo path if found
    repo_root = Path(__file__).resolve().parents[4]
    sim_py = repo_root / "streaming-server" / "stream_server.py"
    if not sim_py.exists():
        # In some layouts, simulator may live under data/streaming-server
        alt = repo_root / "data" / "streaming-server" / "stream_server.py"
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


def read_n_lines(host: str, port: int, n: int, timeout: float = 10.0) -> list[str]:
    deadline = time.time() + timeout
    lines: list[str] = []
    # Retry loop if simulator is still spinning up
    while time.time() < deadline and len(lines) < n:
        try:
            with socket.create_connection((host, port), timeout=1.0) as s:
                buf = b""
                while len(lines) < n and time.time() < deadline:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf and len(lines) < n:
                        line, buf = buf.split(b"\n", 1)
                        if line.strip():
                            lines.append(line.decode("utf-8", errors="ignore"))
                break
        except OSError:
            time.sleep(0.3)
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Project Sentinel demo runner")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--limit", type=int, default=10, help="sample N events to write")
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

        lines = read_n_lines(args.host, args.port, args.limit)
        if not lines:
            print("[error] No events received from stream; exiting with failure.")
            return 2

        out_path = results_dir / "events.jsonl"
        print(f"[info] Writing {len(lines)} events to {out_path}")
        with out_path.open("w", encoding="utf-8") as f:
            for ln in lines:
                # For now, write the line as-is; real pipeline would normalize and detect events
                try:
                    json.loads(ln)  # sanity check valid JSON
                    f.write(ln + "\n")
                except json.JSONDecodeError:
                    # Write a wrapped object if banner or non-JSON present
                    f.write(json.dumps({"raw": ln}) + "\n")
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
