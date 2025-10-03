#!/usr/bin/env python3
"""Simple JSON event replay service for Project Sentinel datasets.

This server streams all JSON datasets found in the project `data/`
directory as a single, chronologically sorted feed. Each connected client
receives newline-delimited JSON objects that report the dataset name,
sequence number, adjusted timestamp, and payload.

The implementation uses only Python's standard library so it runs on
Windows, macOS, and Linux without additional dependencies.

Example usage:
    python stream_server.py --port 8765 --speed 1.0
    python stream_server.py --datasets POS_Transactions Queue_monitor --speed 25 --loop
"""

from __future__ import annotations

import argparse
import json
import logging
import socketserver
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional


DATASET_ALIASES: Dict[str, str] = {
    "POS_Transactions": "pos_transactions",
    "RFID_data": "rfid_readings",
    "Queue_monitor": "queue_monitoring",
    "Product_recognism": "product_recognition",
    "Current_inventory_data": "inventory_snapshots",
}
FILENAME_TO_CANONICAL: Dict[str, str] = {v: k for k, v in DATASET_ALIASES.items()}
EXCLUDE_DATASETS = {"events"}


def resolve_dataset_path(data_root: Path, name: str) -> Path:
    """Resolve a dataset identifier to a concrete file path."""

    candidates = []
    search_keys = []
    alias = DATASET_ALIASES.get(name)
    if alias:
        search_keys.append(alias)
    search_keys.append(name)

    for key in search_keys:
        stem = key.rstrip("/")
        if not stem:
            continue
        for suffix in (".jsonl", ".json"):
            candidate = data_root / f"{stem}{suffix}"
            if candidate.exists():
                return candidate
            candidates.append(candidate)

    attempted = ", ".join(str(path) for path in candidates)
    raise SystemExit(f"Dataset file not found. Tried: {attempted}")


def discover_dataset_paths(data_root: Path) -> List[Path]:
    """Return all dataset files under the root, preferring JSONL when present."""

    discovered: Dict[str, Path] = {}
    for pattern in ("*.jsonl", "*.json"):
        for path in sorted(data_root.glob(pattern)):
            stem = path.stem
            if stem in EXCLUDE_DATASETS:
                continue
            if stem in discovered:
                continue
            discovered[stem] = path
    return list(discovered.values())

LOGGER = logging.getLogger("stream_server")


def load_events(dataset_path: Path) -> List[Dict[str, Any]]:
    """Load events from the JSON dataset.

    Supports list-based JSON files, dictionaries with an `events` list,
    JSONL files, or single JSON objects (which are treated as single events).
    """
    with dataset_path.open("r", encoding="utf-8") as handle:
        try:
            payload = json.load(handle)
        except json.JSONDecodeError:
            handle.seek(0)
            payload = [json.loads(line) for line in handle if line.strip()]

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "events" in payload and isinstance(payload["events"], list):
            return payload["events"]
        # If it's a single JSON object (like inventory snapshot), treat it as a single event
        return [payload]

    raise ValueError(
        f"Unsupported JSON structure in {dataset_path}. Expected a list of events, a dict with 'events' key, or a single event object."
    )


def parse_timestamp(value: Any, dataset: str, source: Path) -> datetime:
    if not isinstance(value, str):
        raise ValueError(
            f"Event in {dataset} ({source}) is missing a string timestamp: {value!r}"
        )
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"Unable to parse timestamp '{value}' in dataset {dataset} ({source})"
        ) from exc


def collect_events(
    dataset_paths: Iterable[Path],
) -> tuple[List[Dict[str, Any]], List[str]]:
    """Load and sort all events from the provided dataset files."""

    all_events: List[Dict[str, Any]] = []
    dataset_names: List[str] = []

    for path in dataset_paths:
        dataset_name = FILENAME_TO_CANONICAL.get(path.stem, path.stem)
        dataset_names.append(dataset_name)
        raw_events = load_events(path)
        if not raw_events:
            LOGGER.warning("Dataset %s contained no events", path)
            continue

        for event in raw_events:
            ts = parse_timestamp(event.get("timestamp"), dataset_name, path)
            all_events.append(
                {
                    "dataset": dataset_name,
                    "timestamp": ts,
                    "payload": event,
                }
            )

    if not all_events:
        raise ValueError("No events found across provided datasets.")

    all_events.sort(key=lambda item: item["timestamp"])
    return all_events, dataset_names


class EventStreamRequestHandler(socketserver.BaseRequestHandler):
    """Handle an inbound TCP connection and stream events."""

    def handle(self) -> None:  # type: ignore[override]
        server: ReplayTCPServer = self.server  # type: ignore[assignment]
        client_host, client_port = self.client_address
        LOGGER.info("Client connected from %s:%s", client_host, client_port)

        # Send a short banner on connection.
        banner = {
            "service": "project-sentinel-event-stream",
            "datasets": server.dataset_names,
            "events": len(server.events),
            "loop": server.loop,
            "speed_factor": server.speed,
            "cycle_seconds": server.cycle_span.total_seconds(),
            "schema": "newline-delimited JSON objects",
        }
        self.request.sendall(json.dumps(banner).encode("utf-8") + b"\n")

        try:
            loop_index = 0
            previous_emitted: Optional[datetime] = None
            sequence = 1
            while True:
                LOGGER.info("Starting loop cycle %d", loop_index + 1)
                for record in server.events:
                    adjusted_timestamp: datetime = record["timestamp"] + (
                        server.cycle_span * loop_index
                    )

                    if previous_emitted is not None:
                        delta = (adjusted_timestamp - previous_emitted).total_seconds()
                        adjusted = delta / server.speed if server.speed > 0 else 0
                        # Ensure minimum gap between events to prevent flooding
                        if adjusted <= 0:
                            adjusted = 0.1 / server.speed  # Minimum 0.1 second gap at 1x speed
                        time.sleep(adjusted)
                    previous_emitted = adjusted_timestamp

                    original_timestamp = record["payload"].get("timestamp")
                    event_copy = dict(record["payload"])
                    event_copy["timestamp"] = adjusted_timestamp.isoformat()

                    frame = {
                        "dataset": record["dataset"],
                        "sequence": sequence,
                        "timestamp": adjusted_timestamp.isoformat(),
                        "original_timestamp": original_timestamp,
                        "event": event_copy,
                    }
                    self.request.sendall(json.dumps(frame).encode("utf-8") + b"\n")
                    sequence += 1

                if not server.loop:
                    LOGGER.info("Loop disabled, ending stream")
                    break

                loop_index += 1
                LOGGER.info("Completed loop cycle %d, starting next cycle", loop_index)
        except (BrokenPipeError, ConnectionResetError):
            LOGGER.info("Client %s:%s disconnected", client_host, client_port)
        finally:
            LOGGER.info("Stream to %s:%s ended", client_host, client_port)


class ReplayTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        events: Iterable[Dict[str, Any]],
        dataset_names: List[str],
        speed: float,
        loop: bool,
        cycle_span: timedelta,
    ) -> None:
        super().__init__(server_address, EventStreamRequestHandler)
        self.events: List[Dict[str, Any]] = list(events)
        self.dataset_names = dataset_names
        self.speed = speed
        self.loop = loop
        self.cycle_span = cycle_span


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay Project Sentinel JSON datasets over a TCP stream",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-root",
        default=Path(__file__).resolve().parent.parent / "input",
        type=Path,
        help="Root directory containing JSON datasets",
    )
    parser.add_argument(
        "--datasets",
        nargs="*",
        help="Optional subset of dataset names (canonical or filename stem). Defaults to all JSON/JSONL files in data-root.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="TCP port to expose the stream",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind address (use 127.0.0.1 to restrict to local machine)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Replay speed multiplier (1.0 = real-time). Allowable range: 1 to 100.",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Continuously loop the dataset instead of closing after one pass",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Logging verbosity",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if not (1.0 <= args.speed <= 100.0):
        raise SystemExit("--speed must be between 1 and 100")

    if not args.data_root.exists():
        raise SystemExit(f"Data directory not found: {args.data_root}")

    if args.datasets:
        dataset_paths = [resolve_dataset_path(args.data_root, name) for name in args.datasets]
    else:
        dataset_paths = discover_dataset_paths(args.data_root)

    if not dataset_paths:
        raise SystemExit("No dataset files found to stream.")

    events, dataset_names = collect_events(dataset_paths)

    first_timestamp = events[0]["timestamp"]
    last_timestamp = events[-1]["timestamp"]

    min_gap: Optional[timedelta] = None
    for idx in range(len(events) - 1):
        gap = events[idx + 1]["timestamp"] - events[idx]["timestamp"]
        if gap.total_seconds() <= 0:
            continue
        if min_gap is None or gap < min_gap:
            min_gap = gap

    if min_gap is None:
        min_gap = timedelta(seconds=1)

    # Calculate cycle duration as the time span from first to last event
    # This ensures the next cycle starts immediately after the last event
    cycle_span = (last_timestamp - first_timestamp) + min_gap
    if cycle_span.total_seconds() <= 0:
        cycle_span = timedelta(seconds=1)

    LOGGER.info(
        "Loaded %s combined events from %s dataset(s) (loop=%s, speed=%sx, cycle=%ss)",
        len(events),
        len(dataset_names),
        args.loop,
        args.speed,
        cycle_span.total_seconds(),
    )

    server = ReplayTCPServer(
        (args.host, args.port),
        events=events,
        dataset_names=dataset_names,
        speed=args.speed,
        loop=args.loop,
        cycle_span=cycle_span,
    )

    LOGGER.info("Starting event stream on %s:%s", args.host, args.port)

    try:
        with server:
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()

            LOGGER.info("Server ready. Press Ctrl+C to stop.")
            while server_thread.is_alive():
                time.sleep(0.5)
    except KeyboardInterrupt:
        LOGGER.info("Shutting down server")
        server.shutdown()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
