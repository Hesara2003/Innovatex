# Project Sentinel 🛡️

> Real-time retail analytics command center for queue management, shrinkage detection, and customer experience optimization

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![No Dependencies](https://img.shields.io/badge/dependencies-none-green.svg)](requirements.txt)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🎯 Overview

Project Sentinel is a real-time command center that fuses queue sensors, POS, RFID, and vision data into one actionable dashboard. It eliminates the 40% wait-time variance at peak hours and reduces shrinkage by 60% on flagged items through instant detection and alerts.

### Key Features

- **🔍 Real-Time Detection**: 6 detection algorithms for queue health, scanner avoidance, barcode switching, weight discrepancies, inventory issues, and system errors
- **📊 Live Dashboard**: Beautiful HTML dashboard with queue metrics, alerts, and CX scores updating every 3 seconds
- **🌊 Stream Processing**: High-performance TCP stream server for event replay and real-time data ingestion
- **🚀 Zero Dependencies**: Built entirely with Python standard library - no external packages required
- **📡 RESTful API**: Complete HTTP API for dashboard integration and third-party tools

## 🚀 Quick Start

### Prerequisites

- Python 3.13+ (no external packages needed!)
- Modern web browser (for dashboard)

### Launch Demo (1 Command)

```bash
# Windows
start_demo.bat

# Or manually
py src/integration/api_server.py --seed-demo
```

Then open `src/dashboard/simple_dashboard.html` in your browser.

### Stream Real-Time Data

```bash
# Terminal 1: Start stream server
py data/streaming-server/stream_server.py --loop --speed 10

# Terminal 2: Connect client
py scripts/stream_client.py
```

## 📁 Project Structure

```
Innovatex/
├── src/
│   ├── analytics/          # Queue metrics, inventory analysis, event correlation
│   ├── detection/          # 6 detection algorithms
│   ├── pipeline/           # Data transformation and enrichment
│   ├── io/                 # Stream reader utilities
│   ├── integration/        # API server
│   └── dashboard/          # HTML dashboard + components
├── data/
│   ├── input/              # JSONL datasets (6 files, 1.9MB)
│   └── streaming-server/   # TCP stream server
├── scripts/
│   ├── demo_server.py      # Simple TCP demo server
│   ├── test_api.py         # API endpoint tester
│   ├── test_client.py      # TCP client tester
│   └── stream_client.py    # Stream server client
├── tests/                  # Unit and integration tests
├── run_demo.py             # Offline demo runner
├── start_demo.bat          # Quick launcher (Windows)
└── start_demo.ps1          # Quick launcher (PowerShell)
```

## 🎮 Usage

### 1. API Server

The API server powers the dashboard with real-time metrics:

```bash
# Start with seed data
py src/integration/api_server.py --seed-demo

# Production mode
py src/integration/api_server.py --host 0.0.0.0 --port 5000
```

**Endpoints:**
- `GET /api/dashboard` - Complete dashboard data
- `GET /api/alerts` - Detection events and incidents
- `GET /api/queue-health` - Queue metrics by station
- `GET /api/correlations` - Event correlation summary

### 2. Stream Server

Replay datasets as a chronological TCP stream:

```bash
# Default: all datasets at 1x speed
py data/streaming-server/stream_server.py

# Custom: specific datasets at 25x speed with looping
py data/streaming-server/stream_server.py \
    --datasets POS_Transactions Queue_monitor \
    --speed 25 \
    --loop
```

### 3. Offline Analysis

Process datasets offline and generate alerts:

```bash
# Process all datasets
py run_demo.py

# Limit events and specify datasets
py run_demo.py --limit 1000 --datasets queue_monitoring pos_transactions

# With evaluation against reference
py run_demo.py --reference data/input/events.jsonl --eval-fields dataset sku
```

Outputs:
- `results/events.jsonl` - Normalized and enriched events
- `results/alerts.jsonl` - Detection alerts

### 4. Testing Tools

```bash
# Test API endpoints
py scripts/test_api.py

# Test TCP demo server
py scripts/demo_server.py              # Terminal 1
py scripts/test_client.py              # Terminal 2

# Monitor stream
py scripts/stream_client.py localhost 8765
```

## 🔍 Detection Algorithms

| Algorithm | Description | Alert Type |
|-----------|-------------|------------|
| **Queue Health** | Detects queue spikes (>6 customers) and extended wait times (>120s) | `queue_spike`, `extended_wait` |
| **Scanner Avoidance** | Identifies customers scanning few items vs. leaving with many | `scanner_avoidance` |
| **Barcode Switching** | Flags mismatches between vision, RFID, and POS scans | `barcode_switch` |
| **Weight Discrepancy** | Compares actual weight against expected product weight | `weight_mismatch` |
| **Inventory Discrepancy** | Detects stock-level anomalies vs. expected levels | `inventory_anomaly` |
| **System Health** | Monitors for scanner errors, offline status, crashes | `system_error` |

## 📊 Data Pipeline

```
JSONL Datasets → Load & Normalize → Enrich (Products/Customers) → Detection → Alerts
                                 ↓
                         Stream Server (Real-time)
                                 ↓
                         API Server ← Dashboard
```

**Supported Datasets:**
- `queue_monitoring.jsonl` - Queue sensor data (993KB)
- `pos_transactions.jsonl` - Point-of-sale events (60KB)
- `rfid_readings.jsonl` - RFID tag scans (782KB)
- `product_recognition.jsonl` - Computer vision results (37KB)
- `inventory_snapshots.jsonl` - Stock levels (11KB)

## 🛠️ Development

### Running Tests

```bash
# All tests
py -m pytest tests/

# Specific test suite
py -m pytest tests/test_detectors.py -v

# With coverage
py -m pytest --cov=src tests/
```

### Code Structure

**Detection Pattern:**
```python
from src.pipeline.transform import SentinelEvent

def detect_issue(event: SentinelEvent) -> List[dict]:
    # Analysis logic
    if condition_met:
        return [{
            "type": "alert_type",
            "station_id": event.station_id,
            "timestamp": event.timestamp.isoformat(),
            "confidence": 0.85,
            "evidence": {...},
            "recommended_action": "..."
        }]
    return []
```

## 📈 Performance

- **Stream Server**: Handles 100+ events/sec at configurable speeds (1x - 100x)
- **API Response**: < 50ms for dashboard endpoint
- **Detection Latency**: Real-time processing < 10ms per event
- **Memory Footprint**: < 100MB for typical workloads

## 🎯 Demo Script (2 Minutes)

Perfect for presentations:

1. **Start Services** (15s)
   ```bash
   start_demo.bat
   ```

2. **Show Dashboard** (60s)
   - Overall CX score: 78
   - Queue stations with live metrics
   - Suspicious checkout alerts
   - Inventory shrinkage values

3. **Explain Impact** (30s)
   - 40% reduction in queue wait-time variance
   - 60% shrinkage reduction on flagged items
   - Real-time CX incident triggering

4. **Technical Stack** (15s)
   - Pure Python, lightweight HTML dashboard
   - No external dependencies
   - Ready for rapid rollout

## 🤝 Contributing

This is a hackathon project for Project Sentinel. For team collaboration:

1. Check `TEAM_BRANCHES.md` for branch strategy
2. Follow `RUNBOOK_GIT.md` for git workflows
3. Review `DEMO_SCRIPT.md` for presentation guidelines

## 📝 License

MIT License - see LICENSE file for details

## 🎓 Acknowledgments

Built for the retail analytics challenge focusing on:
- Queue management optimization
- Shrinkage reduction through ML/vision
- Real-time CX analytics
- Cross-team workflow automation

## 📞 Support

For questions or issues:
- Check `getting-started.md` for setup help
- Review `STATUS_REPORT.md` for known issues
- See test files for usage examples

---

**Project Sentinel** - Making every store lead's shift start with actionable intelligence 🎯
