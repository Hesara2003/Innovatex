"""Built-in HTTP server that powers Project Sentinel's CX dashboard."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections import deque
from datetime import datetime, timezone, timedelta
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
        elif parsed.path == "/api/integration/stream-reader-status":
            self._handle_stream_reader_status()
        elif parsed.path == "/api/integration/evaluation-metrics":
            self._handle_evaluation_metrics()
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
            "stream_reader": STATE["stream_reader_status"],
            "evaluation_metrics": STATE["evaluation_metrics"],
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

    def _handle_stream_reader_status(self) -> None:
        payload = self._read_json()
        status = STATE.get("stream_reader_status")
        if not isinstance(status, dict):
            status = {}
        payload.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        if payload.get("last_heartbeat") is None and payload.get("updated_at"):
            payload["last_heartbeat"] = payload["updated_at"]
        STATE["stream_reader_status"] = {**status, **payload}
        self._send_json({"status": "ok"})

    def _handle_evaluation_metrics(self) -> None:
        payload = self._read_json()
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        STATE["evaluation_metrics"] = payload
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


STATE: Dict[str, object] = {
    "detection_events": deque(maxlen=200),
    "stream_events": deque(maxlen=400),
    "inventory_reports": deque(maxlen=10),
    "enriched_insights": deque(maxlen=40),
    "stream_heartbeat": deque(maxlen=900),
    "stream_dataset_recent": deque(maxlen=200),
    "stream_dataset_last_seen": {},
    "stream_reader_status": {
        "connected": False,
        "processed_events": 0,
        "latency_ms": None,
        "last_heartbeat": None,
        "notes": "",
    },
    "evaluation_metrics": None,
}


def record_stream_event(dataset: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    STATE["stream_heartbeat"].append(now)
    if dataset:
        dataset_key = str(dataset)
        STATE["stream_dataset_recent"].append((now, dataset_key))
        dataset_last_seen = STATE.get("stream_dataset_last_seen")
        if isinstance(dataset_last_seen, dict):
            dataset_last_seen[dataset_key] = now.isoformat()


def compute_stream_health(window_seconds: int = 60) -> Dict[str, object]:
    now = datetime.now(timezone.utc)
    timestamps: Deque[datetime] = STATE["stream_heartbeat"]

    while timestamps and (now - timestamps[0]).total_seconds() > 1800:
        timestamps.popleft()

    recent = [ts for ts in timestamps if (now - ts).total_seconds() <= window_seconds]
    events_last_minute = len(recent)
    events_per_minute = round((events_last_minute / window_seconds) * 60, 2) if window_seconds > 0 else 0.0
    last_event_age = (now - timestamps[-1]).total_seconds() if timestamps else None

    dataset_events_raw = list(STATE["stream_dataset_recent"])
    dataset_events: List[tuple[datetime, str]] = []
    for entry in dataset_events_raw:
        if isinstance(entry, tuple) and len(entry) == 2 and isinstance(entry[0], datetime):
            dataset_events.append((entry[0], str(entry[1])))
        else:
            dataset_events.append((now, str(entry)))
    dataset_counts_1m: Dict[str, int] = {}
    dataset_counts_15m: Dict[str, int] = {}
    datasets_last_seen = STATE.get("stream_dataset_last_seen", {})

    trimmed: List[tuple[datetime, str]] = []
    for ts, name in dataset_events:
        age = (now - ts).total_seconds()
        if age <= 1800:
            trimmed.append((ts, name))
            if age <= 60:
                dataset_counts_1m[name] = dataset_counts_1m.get(name, 0) + 1
            if age <= 900:
                dataset_counts_15m[name] = dataset_counts_15m.get(name, 0) + 1
    STATE["stream_dataset_recent"] = deque(trimmed, maxlen=200)

    dataset_trends = []
    for name in sorted({n for _, n in trimmed}):
        last_seen_iso = datasets_last_seen.get(name)
        last_seen_seconds = None
        if last_seen_iso:
            try:
                last_seen_dt = datetime.fromisoformat(str(last_seen_iso))
                last_seen_seconds = round((now - last_seen_dt).total_seconds(), 1)
            except ValueError:
                last_seen_seconds = None
        dataset_trends.append(
            {
                "dataset": name,
                "events_last_minute": dataset_counts_1m.get(name, 0),
                "events_last_15_minutes": dataset_counts_15m.get(name, 0),
                "last_seen": last_seen_iso,
                "last_seen_seconds_ago": last_seen_seconds,
            }
        )

    active_datasets = [trend["dataset"] for trend in dataset_trends]

    reader_status = STATE.get("stream_reader_status", {})
    if isinstance(reader_status, dict) and reader_status.get("last_heartbeat"):
        try:
            last_hb = datetime.fromisoformat(str(reader_status["last_heartbeat"]))
            reader_status = {
                **reader_status,
                "seconds_since_heartbeat": round((now - last_hb).total_seconds(), 1),
            }
        except ValueError:
            reader_status = {
                **reader_status,
                "seconds_since_heartbeat": None,
            }

    return {
        "events_last_minute": events_last_minute,
        "events_per_minute": events_per_minute,
        "active_datasets": active_datasets,
        "last_event_seconds_ago": round(last_event_age, 1) if last_event_age is not None else None,
        "datasets": dataset_trends,
        "reader_status": reader_status,
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