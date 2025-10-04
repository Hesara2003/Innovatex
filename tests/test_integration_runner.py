from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = REPO_ROOT / "submission-structure" / "Team##_sentinel" / "evidence" / "executables" / "run_demo.py"
SIMULATOR_PATH = REPO_ROOT / "data" / "streaming-server" / "stream_server.py"


@pytest.mark.skipif(not RUNNER_PATH.exists(), reason="Demo runner script not found")
@pytest.mark.skipif(not SIMULATOR_PATH.exists(), reason="Stream simulator script not available")
def test_run_demo_end_to_end() -> None:
    """Exercise the streaming pipeline via the judge entrypoint."""

    results_dir = RUNNER_PATH.parent / "results"
    if results_dir.exists():
        shutil.rmtree(results_dir)
    results_dir.mkdir(exist_ok=True)

    port = 9876

    sim_proc = subprocess.Popen(
        [sys.executable, str(SIMULATOR_PATH), "--port", str(port), "--speed", "50", "--loop"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        time.sleep(1.0)

        completed = subprocess.run(
            [sys.executable, str(RUNNER_PATH), "--port", str(port), "--limit", "80", "--no-start-sim"],
            capture_output=True,
            text=True,
            check=False,
        )

        assert completed.returncode == 0, f"Runner failed: {completed.stderr or completed.stdout}"

        events_path = results_dir / "events.jsonl"
        insights_path = results_dir / "insights.json"
        raw_path = results_dir / "raw_stream.jsonl"

        assert events_path.exists(), "events.jsonl should be created"
        assert insights_path.exists(), "insights.json should be created"
        assert raw_path.exists(), "raw_stream.jsonl should be created"

        events_lines = [line.strip() for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert events_lines, "events.jsonl must contain at least one record"
        first_detection = json.loads(events_lines[0])
        assert "type" in first_detection
        assert "timestamp" in first_detection

        insights = json.loads(insights_path.read_text(encoding="utf-8"))
        assert "kpis" in insights and isinstance(insights["kpis"], dict)
        assert "additional_insights" in insights and isinstance(insights["additional_insights"], list)

    finally:
        sim_proc.terminate()
        try:
            sim_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            sim_proc.kill()
            sim_proc.wait(timeout=2)
