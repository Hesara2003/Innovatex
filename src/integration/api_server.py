"""Built-in HTTP server that powers Project Sentinel's CX dashboard."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import deque
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Deque, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

ROOT_SRC = Path(__file__).resolve().parents[1]
if str(ROOT_SRC) not in sys.path:
    sys.path.insert(0, str(ROOT_SRC))

from analytics.event_correlation import event_correlator
from analytics.inventory_analysis import inventory_analyzer
from analytics.queue_metrics import queue_metrics_service


LOG = logging.getLogger("sentinel.api")


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "SentinelAPI/1.0"

    def do_OPTIONS(self) -> None:  # noqa: N802 - http handler signature
        self._send_cors_headers()
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - http handler signature
        parsed = urlparse(self.path)
        if parsed.path == "/api/dashboard":
            self._handle_dashboard()
        elif parsed.path == "/api/queue-health":
            self._handle_queue_health(parsed)
        elif parsed.path == "/api/alerts":
            self._handle_alerts()
        elif parsed.path == "/api/correlations":
            self._send_json(event_correlator.build_summary())
        else:
            self._send_not_found()

    def do_POST(self) -> None:  # noqa: N802 - http handler signature
        parsed = urlparse(self.path)
        if parsed.path == "/api/integration/detection-events":
            self._handle_detection_events()
        elif parsed.path == "/api/integration/stream-data":
            self._handle_stream_data()
        elif parsed.path == "/api/integration/inventory-snapshot":
            self._handle_inventory_snapshot()
        elif parsed.path == "/api/integration/enriched-insights":
            self._handle_enriched_insights()
        else:
            self._send_not_found()

    # ------------------------------------------------------------------
    # GET Handlers
    # ------------------------------------------------------------------
    def _handle_dashboard(self) -> None:
        queue_payload = queue_metrics_service.generate_dashboard_payload()
        inventory_latest = STATE["inventory_reports"][-1] if STATE["inventory_reports"] else None
        response = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_status": "ACTIVE",
            "queue": queue_payload,
            "correlations": event_correlator.build_summary(),
            "inventory": inventory_latest,
            "enriched_insights": list(STATE["enriched_insights"])[-5:],
            "stream_health": compute_stream_health(),
        }
        self._send_json(response)

    def _handle_queue_health(self, parsed) -> None:
        query = parse_qs(parsed.query)
        station_id = query.get("station_id", [None])[0]
        if station_id:
            payload = queue_metrics_service.calculate_queue_health(station_id)
        else:
            payload = queue_metrics_service.generate_dashboard_payload()
        self._send_json(payload)

    def _handle_alerts(self) -> None:
        response = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "queue_incidents": queue_metrics_service.get_recent_incidents(limit=20),
            "detection_events": list(STATE["detection_events"])[-20:],
            "suspicious_checkouts": event_correlator.get_recent_suspicious(limit=20),
        }
        self._send_json(response)

    # ------------------------------------------------------------------
    # POST Handlers
    # ------------------------------------------------------------------
    def _handle_detection_events(self) -> None:
        payload = self._read_json()
        events = payload.get("events") or []
        for event in events:
            normalized = {
                "timestamp": event.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "station_id": event.get("station_id", "UNKNOWN"),
                "details": event,
            }
            STATE["detection_events"].append(normalized)
        self._send_json({"status": "ok", "received": len(events)})

    def _handle_stream_data(self) -> None:
        payload = self._read_json()
        dataset = str(payload.get("dataset", "")).lower()
        STATE["stream_events"].append(payload)
        record_stream_event(dataset or None)

        observation = self._extract_queue_observation(payload)
        routed_queue = False

        if dataset in {"queue_monitor", "queue_monitoring", "queue"} and observation:
            queue_metrics_service.ingest_observation(payload.get("station_id"), observation)
            routed_queue = True

        if not routed_queue and dataset in {"pos_transactions", "rfid_readings", "product_recognition"}:
            event_correlator.register_event(dataset, payload)
        elif not routed_queue:
            if observation:
                queue_metrics_service.ingest_observation(payload.get("station_id"), observation)
            else:
                event_correlator.register_event(dataset or "stream", payload)

        self._send_json({"status": "processed"})

    def _handle_inventory_snapshot(self) -> None:
        payload = self._read_json()
        baseline = payload.get("baseline", {})
        actual = payload.get("actual", {})
        sales = payload.get("sales", [])
        restocks = payload.get("restocks", [])
        report = inventory_analyzer.analyze(baseline, actual, sales, restocks)
        STATE["inventory_reports"].append(report)
        self._send_json({"status": "ok", "report": report})

    def _handle_enriched_insights(self) -> None:
        payload = self._read_json()
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        STATE["enriched_insights"].append(payload)
        self._send_json({"status": "ok"})

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _extract_queue_observation(self, payload: Dict[str, object]) -> Optional[Dict[str, object]]:
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        return {
            "timestamp": payload.get("timestamp"),
            "customer_count": data.get("customer_count"),
            "average_dwell_time": data.get("average_dwell_time"),
            "status": payload.get("status", "active"),
        }

    def _read_json(self) -> Dict[str, object]:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, status=HTTPStatus.BAD_REQUEST)
            raise

    def _send_json(self, data: Dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_not_found(self) -> None:
        self._send_json({"error": "Endpoint not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, fmt: str, *args) -> None:
        LOG.info("%s - %s", self.address_string(), fmt % args)

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


STATE: Dict[str, Deque] = {
    "detection_events": deque(maxlen=200),
    "stream_events": deque(maxlen=400),
    "inventory_reports": deque(maxlen=10),
    "enriched_insights": deque(maxlen=40),
    "stream_heartbeat": deque(maxlen=900),
    "stream_dataset_recent": deque(maxlen=200),
}


def record_stream_event(dataset: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    STATE["stream_heartbeat"].append(now)
    if dataset:
        STATE["stream_dataset_recent"].append(str(dataset))


def compute_stream_health(window_seconds: int = 60) -> Dict[str, object]:
    now = datetime.now(timezone.utc)
    timestamps = STATE["stream_heartbeat"]

    while timestamps and (now - timestamps[0]).total_seconds() > 600:
        timestamps.popleft()

    recent = [ts for ts in timestamps if (now - ts).total_seconds() <= window_seconds]
    events_last_minute = len(recent)
    events_per_minute = round((events_last_minute / window_seconds) * 60, 2) if window_seconds > 0 else 0.0
    last_event_age = (now - timestamps[-1]).total_seconds() if timestamps else None

    datasets_window = list(STATE["stream_dataset_recent"])[-100:]
    active_datasets = sorted({name for name in datasets_window if name})

    return {
        "events_last_minute": events_last_minute,
        "events_per_minute": events_per_minute,
        "active_datasets": active_datasets,
        "last_event_seconds_ago": round(last_event_age, 1) if last_event_age is not None else None,
    }


def seed_demo_data(samples: int = 5) -> None:
    """Optional helper to load a few sample events from /data/input."""

    data_root = Path(__file__).resolve().parents[2] / "data" / "input"
    files = [
        ("queue_monitoring.jsonl", "queue_monitor"),
        ("pos_transactions.jsonl", "pos_transactions"),
        ("rfid_readings.jsonl", "rfid_readings"),
        ("product_recognition.jsonl", "product_recognition"),
    ]

    for file_name, dataset in files:
        file_path = data_root / file_name
        if not file_path.exists():
            continue
        with file_path.open("r", encoding="utf-8") as handle:
            for idx, line in enumerate(handle):
                if idx >= samples:
                    break
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event["dataset"] = dataset
                record_stream_event(dataset)
                if dataset == "queue_monitor":
                    observation = {
                        "timestamp": event.get("timestamp"),
                        "customer_count": event.get("data", {}).get("customer_count"),
                        "average_dwell_time": event.get("data", {}).get("average_dwell_time"),
                        "status": event.get("status", "active"),
                    }
                    queue_metrics_service.ingest_observation(event.get("station_id"), observation)
                else:
                    event_correlator.register_event(dataset, event)


def run_api_server(host: str, port: int, seed: bool = False) -> None:
    if seed:
        seed_demo_data()

    with ThreadingHTTPServer((host, port), DashboardRequestHandler) as httpd:
        LOG.info("API server listening on http://%s:%s", host if host != "0.0.0.0" else "localhost", port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            LOG.info("Shutting down API server")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project Sentinel API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="TCP port (default: 5000)")
    parser.add_argument("--seed-demo", action="store_true", help="Load a handful of sample events on startup")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], help="Logging verbosity")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")
    run_api_server(args.host, args.port, seed=args.seed_demo)


if __name__ == "__main__":
    main()