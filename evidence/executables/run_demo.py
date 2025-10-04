#!/usr/bin/env python3
"""Project Sentinel demo runner.

This script delivers a single-command experience for judges:

* boots the built-in HTTP API server (standard library only)
* seeds it with representative queue, correlation, and inventory events
* captures dashboard payloads + alerts into evidence/output artifacts
* writes lightweight placeholder screenshots for the evidence bundle

Usage:
    python evidence/executables/run_demo.py

Optional flags:
    --port 6000            Run the API server on a custom port (default 5000)
    --no-server            Assume the API server is already running
    --seed-demo            Ask the API server to preload sample data on boot
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from http.client import HTTPConnection
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
API_SERVER = ROOT / "src" / "integration" / "api_server.py"
EVIDENCE_ROOT = ROOT / "evidence"
OUTPUT_TEST = EVIDENCE_ROOT / "output" / "test" / "events.jsonl"
OUTPUT_FINAL = EVIDENCE_ROOT / "output" / "final" / "events.jsonl"
SCREENSHOT_DIR = EVIDENCE_ROOT / "screenshots"

PLACEHOLDER_PNGS: Dict[str, bytes] = {
    "dashboard-normal": base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAAEklEQVR4nGNgYGAAAAAEAAHiIbwzAAAAAElFTkSuQmCC"
    ),
    "dashboard-alert": base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAukB9YkO9CsAAAAASUVORK5CYII="
    ),
}

ISO_8601_SECONDS = "%Y-%m-%dT%H:%M:%S"


def ensure_directories() -> None:
    for path in [
        EVIDENCE_ROOT,
        EVIDENCE_ROOT / "output",
        OUTPUT_TEST.parent,
        OUTPUT_FINAL.parent,
        SCREENSHOT_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def start_api_server(port: int, seed_demo: bool) -> subprocess.Popen | None:
    if not API_SERVER.exists():
        raise FileNotFoundError(f"API server not found at {API_SERVER}")

    args = [sys.executable, str(API_SERVER), "--host", "127.0.0.1", "--port", str(port)]
    if seed_demo:
        args.append("--seed-demo")

    process = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process


def stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


def wait_for_server(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = HTTPConnection(host, port, timeout=1.5)
            conn.request("GET", "/api/dashboard")
            response = conn.getresponse()
            response.read()
            conn.close()
            if response.status < 500:
                return True
        except OSError:
            time.sleep(0.4)
    return False


def post_json(url: str, payload: Dict[str, object]) -> Dict[str, object]:
    parsed = urlparse(url)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    data = json.dumps(payload).encode("utf-8")
    conn.request(
        "POST",
        parsed.path,
        body=data,
        headers={"Content-Type": "application/json", "Content-Length": str(len(data))},
    )
    response = conn.getresponse()
    body = response.read()
    conn.close()
    if not body:
        return {}
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}


def get_json(url: str) -> Dict[str, object]:
    parsed = urlparse(url)
    conn = HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    conn.request("GET", parsed.path)
    response = conn.getresponse()
    body = response.read()
    conn.close()
    if not body:
        return {}
    return json.loads(body.decode("utf-8"))


def write_jsonl(path: Path, records: Iterable[Dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def create_placeholder_screenshots() -> List[str]:
    created: List[str] = []
    for name, payload in PLACEHOLDER_PNGS.items():
        target = SCREENSHOT_DIR / f"{name}.png"
        target.write_bytes(payload)
        created.append(str(target))
    return created


def seed_sample_events(port: int) -> None:
    base = f"http://127.0.0.1:{port}"

    queue_samples = [
        {
            "dataset": "queue_monitor",
            "station_id": "SCC1",
            "timestamp": time.strftime(ISO_8601_SECONDS),
            "status": "Active",
            "data": {"customer_count": 9, "average_dwell_time": 320.0},
        },
        {
            "dataset": "queue_monitor",
            "station_id": "SCC2",
            "timestamp": time.strftime(ISO_8601_SECONDS),
            "status": "Active",
            "data": {"customer_count": 4, "average_dwell_time": 210.0},
        },
        {
            "dataset": "queue_monitor",
            "station_id": "SCC3",
            "timestamp": time.strftime(ISO_8601_SECONDS),
            "status": "Active",
            "data": {"customer_count": 2, "average_dwell_time": 110.0},
        },
    ]
    for sample in queue_samples:
        post_json(f"{base}/api/integration/stream-data", sample)

    # POS + RFID + Vision events for correlation
    correlation_bundle = [
        {
            "dataset": "pos_transactions",
            "station_id": "SCC1",
            "timestamp": time.strftime(ISO_8601_SECONDS),
            "status": "Active",
            "data": {
                "customer_id": "C045",
                "sku": "PRD_F_14",
                "price": 540.0,
            },
        },
        {
            "dataset": "rfid_readings",
            "station_id": "SCC1",
            "timestamp": time.strftime(ISO_8601_SECONDS),
            "status": "Active",
            "data": {"sku": "PRD_F_14", "location": "IN_SCAN_AREA"},
        },
        {
            "dataset": "product_recognition",
            "station_id": "SCC1",
            "timestamp": time.strftime(ISO_8601_SECONDS),
            "status": "Active",
            "data": {"predicted_product": "PRD_F_14", "accuracy": 0.91},
        },
        {
            "dataset": "pos_transactions",
            "station_id": "SCC2",
        "timestamp": time.strftime(ISO_8601_SECONDS),
            "status": "Active",
            "data": {
                "customer_id": "C099",
                "sku": "PRD_X_HIGH",
                "price": 4200.0,
            },
        },
    ]

    for event in correlation_bundle:
        post_json(f"{base}/api/integration/stream-data", event)

    detection_events = {
        "events": [
            {
                "station_id": "SCC2",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "type": "scanner_avoidance",
                "confidence": 0.82,
                "notes": "Customer bypassed RFID field",
            }
        ]
    }
    post_json(f"{base}/api/integration/detection-events", detection_events)

    inventory_snapshot = {
        "baseline": {"PRD_F_14": 40, "PRD_X_HIGH": 10},
        "actual": {"PRD_F_14": 33, "PRD_X_HIGH": 5},
        "sales": [
            {"sku": "PRD_F_14", "quantity": 4},
            {"sku": "PRD_X_HIGH", "quantity": 3},
        ],
        "restocks": [{"sku": "PRD_F_14", "quantity": 2}],
    }
    post_json(f"{base}/api/integration/inventory-snapshot", inventory_snapshot)

    enriched_insight = {
        "analyst": "Sandil",
        "focus": "basket_value",
        "insight": "Station 2 checkout mismatch flagged for manual review.",
    }
    post_json(f"{base}/api/integration/enriched-insights", enriched_insight)


def capture_outputs(port: int) -> Tuple[Dict[str, object], Dict[str, object]]:
    base = f"http://127.0.0.1:{port}"
    dashboard = get_json(f"{base}/api/dashboard")
    alerts = get_json(f"{base}/api/alerts")
    return dashboard, alerts


def build_records(dashboard: Dict[str, object], alerts: Dict[str, object]) -> List[Dict[str, object]]:
    return [
        {"type": "dashboard", "payload": dashboard},
        {"type": "alerts", "payload": alerts},
    ]


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project Sentinel demo runner")
    parser.add_argument("--port", type=int, default=5000, help="API server port")
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Do not launch the API server (assume it is already running)",
    )
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Ask the API server to preload sample data using --seed-demo",
    )
    args = parser.parse_args(argv)

    ensure_directories()

    proc: subprocess.Popen | None = None
    try:
        if not args.no_server:
            proc = start_api_server(args.port, seed_demo=args.seed_demo)
            if not wait_for_server("127.0.0.1", args.port):
                print("[error] API server failed to start in time", file=sys.stderr)
                return 2
            # Give the event loop a breath so the seed loader can complete
            time.sleep(1.0)
        else:
            if not wait_for_server("127.0.0.1", args.port, timeout=5):
                print("[error] API server not reachable", file=sys.stderr)
                return 2

        seed_sample_events(args.port)
        time.sleep(0.5)
        dashboard, alerts = capture_outputs(args.port)

        records = build_records(dashboard, alerts)
        write_jsonl(OUTPUT_TEST, records)
        write_jsonl(OUTPUT_FINAL, records)
        screenshots = create_placeholder_screenshots()

        print("[ok] Demo artifacts generated:")
        print(f"      {OUTPUT_TEST}")
        print(f"      {OUTPUT_FINAL}")
        for shot in screenshots:
            print(f"      {shot}")
        return 0
    finally:
        stop_process(proc)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
