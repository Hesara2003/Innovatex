#!/usr/bin/env python3
"""Utility script to boot the API server, serve the dashboard frontend, and run tests.

This script streamlines the local workflow:
1. Starts the integration API server (backend) on port 5000.
2. Hosts the static dashboard frontend via ``python -m http.server`` on port 5173.
3. Runs the pytest suite once both services are up.

The script keeps the server processes alive until interrupted (Ctrl+C). All
processes are terminated gracefully on exit.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import time
from http.client import HTTPConnection
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
API_SERVER = ROOT / "src" / "integration" / "api_server.py"
DASHBOARD_DIR = ROOT / "src" / "dashboard"
DEFAULT_API_PORT = 5000
DEFAULT_FRONTEND_PORT = 5173


def _ensure_paths() -> None:
    if not API_SERVER.exists():
        raise FileNotFoundError(f"API server not found at {API_SERVER}")
    if not DASHBOARD_DIR.exists():
        raise FileNotFoundError(f"Dashboard directory not found at {DASHBOARD_DIR}")


def _wait_for_http(host: str, port: int, path: str = "/", timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = HTTPConnection(host, port, timeout=1.5)
            conn.request("GET", path)
            conn.getresponse().read()
            conn.close()
            return True
        except OSError:
            time.sleep(0.5)
    return False


def _start_process(args: list[str], cwd: Optional[Path] = None, env: Optional[dict[str, str]] = None) -> subprocess.Popen:
    return subprocess.Popen(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
    )


def _start_backend(port: int) -> subprocess.Popen:
    cmd = [sys.executable, str(API_SERVER), "--host", "127.0.0.1", "--port", str(port)]
    print(f"[backend] Launching API server on 127.0.0.1:{port}")
    proc = _start_process(cmd)
    if not _wait_for_http("127.0.0.1", port, "/api/dashboard", timeout=20):
        raise RuntimeError("API server failed to respond on time")
    print("[backend] API server is responding")
    return proc


def _start_frontend(port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    cmd = [sys.executable, "-m", "http.server", str(port)]
    print(f"[frontend] Serving dashboard from {DASHBOARD_DIR} on http://127.0.0.1:{port}")
    proc = _start_process(cmd, cwd=DASHBOARD_DIR, env=env)
    if not _wait_for_http("127.0.0.1", port, "/simple_dashboard.html", timeout=10):
        print("[frontend] Warning: dashboard may not yet be reachable (continue anyway)")
    else:
        print("[frontend] Dashboard HTTP server is responding")
    return proc


def _run_tests(pytest_args: list[str]) -> int:
    cmd = [sys.executable, "-m", "pytest"] + pytest_args
    print("[tests] Running pytest")
    proc = subprocess.run(cmd, cwd=str(ROOT))
    return proc.returncode


def _terminate(proc: Optional[subprocess.Popen]) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    with contextlib.suppress(Exception):
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=5)
    if proc.poll() is None:
        with contextlib.suppress(Exception):
            proc.terminate()
            proc.wait(timeout=5)
    if proc.poll() is None:
        with contextlib.suppress(Exception):
            proc.kill()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run backend, frontend, and tests together")
    parser.add_argument("--api-port", type=int, default=DEFAULT_API_PORT, help="Port for the API server (default: 5000)")
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=DEFAULT_FRONTEND_PORT,
        help="Port for the dashboard http.server (default: 5173)",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Keep backend/frontend running after tests until interrupted",
    )
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        help="Extra arguments to pass to pytest (use after --)",
    )
    args = parser.parse_args(argv)

    extra_pytest_args: list[str] = []
    if args.pytest_args:
        if args.pytest_args and args.pytest_args[0] == "--":
            extra_pytest_args = args.pytest_args[1:]
        else:
            extra_pytest_args = args.pytest_args

    _ensure_paths()

    backend_proc: Optional[subprocess.Popen] = None
    frontend_proc: Optional[subprocess.Popen] = None
    try:
        backend_proc = _start_backend(args.api_port)
        frontend_proc = _start_frontend(args.frontend_port)
        exit_code = _run_tests(extra_pytest_args)
        if exit_code == 0:
            print("[tests] Pytest completed successfully")
        else:
            print(f"[tests] Pytest exited with code {exit_code}")
        if args.keep_alive:
            print("[info] Backend and frontend remain running. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                print("\n[info] Received interrupt, shutting down...")
        return exit_code
    finally:
        _terminate(frontend_proc)
        _terminate(backend_proc)
        print("[info] All processes terminated")


if __name__ == "__main__":
    sys.exit(main())
