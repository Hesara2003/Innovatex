#!/usr/bin/env python3
"""Minimal client for the Project Sentinel event stream."""

import argparse
import json
import socket
from typing import Iterator


def read_events(host: str, port: int) -> Iterator[dict]:
    with socket.create_connection((host, port)) as conn:
        # Treat socket as file-like for convenient line iteration.
        with conn.makefile("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                yield json.loads(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consume events from the replay server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--limit", type=int, default=10, help="Stop after N events (0 = unlimited)")
    args = parser.parse_args()

    for idx, event in enumerate(read_events(args.host, args.port), start=1):
        print(f"[{idx}] dataset={event.get('dataset')} sequence={event.get('sequence')}")
        print(json.dumps(event.get("event"), indent=2))
        print("-")
        if args.limit and idx >= args.limit:
            break


if __name__ == "__main__":
    main()
