# Submission Guide

Complete this template before zipping your submission. Keep the file at the
project root.

## Team details
- Team name: ENIGMA
- Members: Hesara Perera, Dilusha Chamika, Sandil Perera, Sandali Sandagomi
- Primary contact email: hesarap3@gmail.com

## Judge run command
Judges will `cd evidence/executables/` and run **one command** on Ubuntu 24.04:

```
python3 run_demo.py --seed-demo
```

Adapt `run_demo.py` to set up dependencies, start any services, ingest data,
and write all artefacts into `./results/` (relative to `evidence/executables/`).
No additional scripts or manual steps are allowed.

## Checklist before zipping and submitting
- Algorithms tagged with `# @algorithm Name | Purpose` comments: Yes — `MultiStreamCorrelation | Correlate RFID, POS, and vision data` & `ShrinkageDetection | Calculate inventory shrinkage` &
`BarcodeSwitchingDetection | Flag barcode vs vision SKU mismatches in real time` &
`InventoryDiscrepancyDetection | Surface stock deviations exceeding absolute/relative thresholds` &
`QueueHealthMonitoring | Track queue length and dwell time spikes for staffing actions` &
`ScannerAvoidanceDetection | Catch RFID movements exiting without matching POS scans` &
`SystemHealthDetection | Flag scanner and service error states from status signals` &
`WeightDiscrepancyDetection | Compare POS item weights against catalog standards` &


- Evidence artefacts present in `evidence/`: Yes — `output/test/events.jsonl`, `output/final/events.jsonl`

- Source code complete under `src/`: Yes
