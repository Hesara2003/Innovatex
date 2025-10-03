# Project Sentinel Data Streaming Simulator

This package contains a lightweight event replay service that streams all
Project Sentinel JSON datasets as a single chronological feed. The goal is to
provide a consistent, language-agnostic stream that mirrors a real-time data
source without requiring any external infrastructure.

The simulator sacrifices complexity for portability:

- **Pure Python, standard library only.** Works on Windows, macOS, or Linux
  with Python 3.9+ preinstalled.
- **Simple TCP protocol.** Each client connection receives newline-delimited
  JSON objects containing the dataset name, sequence number, adjusted and
  original timestamps, plus the payload. Students can connect using any
  language that supports sockets.
- **Configurable cadence.** Replay events using the real timestamp gaps at
  speeds from 1× (real time) up to 100×, with optional looping for
  long-running tests.

## Folder contents

```
data/
├── input/               # JSON/JSONL/CSV artifacts used by the simulator
├── output/              # Ground-truth reference outputs (e.g., events.json)
├── streaming-server/    # Event replay service
└── streaming-clients/   # Sample clients in Python, Node.js, and Java
```

| Location | Purpose |
| --- | --- |
| `input/` | Shared reference datasets (flattened, no subfolders) the server streams by default |
| `output/` | Reference `events.jsonl` showing the complete event schema; provided as an example and not derived from the `input/` data. |
| `streaming-server/stream_server.py` | TCP replay server that broadcasts combined datasets |
| `streaming-clients/client_example.py` | Minimal Python client that prints the first few events |
| `streaming-clients/client_example_node.js` | Node.js sample client using the built-in `net` module |
| `streaming-clients/ClientExample.java` | Java sample client using standard library sockets |

## Input data structure

`input/` contains newline-delimited JSON files that drive the stream plus CSV lookup tables the analytics teams can join against.

### Streaming JSONL files
- `inventory_snapshots.jsonl` – single snapshot event with a `timestamp` and a `data` dictionary mapping every SKU (`PRD_*`) to its on-hand quantity (first frame in each loop)
- `queue_monitoring.jsonl` – dwell-time metrics captured at checkout station SCC1 with `station_id`, `status`, and `data` fields for `customer_count` and `average_dwell_time` (seconds)
- `product_recognition.jsonl` – vision system predictions with `station_id`, `status`, and `data` containing `predicted_product` (SKU) plus an `accuracy` confidence score
- `pos_transactions.jsonl` – POS receipts exposing `station_id`, `status`, and `data` payloads with `customer_id`, `sku`, `product_name`, `barcode`, `price`, and `weight_g`
- `rfid_readings.jsonl` – EPC reads with `station_id`, `status`, and `data` holding `epc`, `location`, and the resolved `sku`

### Reference CSV files
- `products_list.csv` – product catalog keyed by `SKU`; includes barcode, price, weight, and EPC range
- `customer_data.csv` – customer master keyed by `Customer_ID`; includes name and contact details

## Data relationships

- `sku` ties POS transactions and inventory snapshots to `products_list.csv`, while product recognition exposes the same identifier under `data.predicted_product`
- `customer_id` links POS events to `customer_data.csv`
- RFID events provide both the raw `data.epc` and a pre-resolved `data.sku`; the EPC range in `products_list.csv` lets students verify the mapping if needed
- Inventories reflect the net effect of the streaming events within each 10-second replay cycle

## Running the simulator

1. Use Python 3.9+ and start the server from the project root:

   ```bash
   cd data/streaming-server
   python stream_server.py --port 8765 --speed 10 --loop
  python stream_server.py --datasets POS_Transactions Queue_monitor --speed 25 --loop
   ```

   Key flags: `--speed` (1–100), `--datasets` (subset of JSONL stems), `--loop` (repeat cycles with shifted timestamps), `--host` (bind address).

2. Connect with any TCP client. The first line is a banner describing the stream, followed by newline-delimited events. Sample clients:

   ```bash
   cd data/streaming-clients
   python client_example.py --host 127.0.0.1 --port 8765 --limit 5
   node client_example_node.js --host 127.0.0.1 --port 8765 --limit 5
   javac ClientExample.java && java ClientExample --host 127.0.0.1 --port 8765 --limit 5
   ```

   Example output:

   ```text
   --- Stream Banner ---
   Service: project-sentinel-event-stream
   Datasets: Current_inventory_data, POS_Transactions, Product_recognism, Queue_monitor, RFID_data
   Events: 5
   Looping: true
   Speed factor: 10.0
   Cycle seconds: 5.0
   ---------------------
   [1] dataset=Current_inventory_data sequence=1
    timestamp: 2025-08-13T16:00:00
    original : 2025-08-13T16:00:00
   ...
   ```

3. Stop the server with <kbd>Ctrl</kbd>+<kbd>C</kbd>.

## Consuming the stream from other languages

The server emits UTF-8 encoded JSON objects separated by newlines.
Students can:

- Use `netcat` (`nc 127.0.0.1 8765`) to inspect raw traffic.
- Implement a socket client in Java, C++, Go, or JavaScript (Node.js) by
  reading line-delimited JSON and deserializing it with their standard
  libraries.
- Wrap the stream in their own messaging layer if they want REST, gRPC, or
  WebSocket interfaces.

## Extending the simulator

- **Multiple datasets:** run multiple server instances on different ports to
  expose other files from `data/` (e.g., `Current_inventory_data`).
- **Custom ordering:** pre-process or shuffle the loaded JSON list before
  streaming to simulate different scenarios.
- **Dynamic control:** extend `stream_server.py` to accept commands from the
  client (e.g., pause/resume or dataset selection) if needed later in the
  competition.

Feel free to adapt the server to your needs, but this
baseline implementation should be enough to unblock teams quickly.
