# Project Sentinel – 2 Minute Demo Script (Sandali)

## Stopwatch Milestones
- **0:00 – 0:15**: Visual countdown ready, dashboard tab preloaded, API server running.
- **0:15 – 0:45**: Problem framing – queues, shrinkage, fragmented signals.
- **0:45 – 1:20**: Live dashboard walkthrough – queue health, alerts, staffing, suspicious checkout.
- **1:20 – 1:45**: Business impact – 40% faster queues, 60% shrinkage reduction, cross-team workflow.
- **1:45 – 2:00**: Call to action + thank you.

## Spoken Narrative

### Opening (0:00 – 0:45)
1. **Problem (15s)** – “Retail execs tell us the queue is the make-or-break moment, yet they monitor it through siloed dashboards. Shrinkage, scanner avoidance and slow stations are caught hours later.”
2. **Consequence (15s)** – “That delay drives 40% higher wait-times at peak and lets high-value items vanish. Store managers are firefighting instead of leading.”
3. **Hook (15s)** – “Project Sentinel is our real-time command center. We fuse queue sensors, POS, RFID, and vision into one actionable canvas powered by Sandali’s CX analytics.”

### Live Demo (0:45 – 1:20)
1. **Overall Pulse (10s)** – Highlight the Store Pulse panel: “Overall CX score is 78. Staffing tile says open one more station; everything updates every three seconds.”
2. **Station Cards (15s)** – Click the highest-risk station: “SCC1 is bright amber—9 guests waiting, dwell time 320s. Service rate is lagging, so we trigger a CX incident.”
3. **Alerts Panel (10s)** – “Alerts stack chronologically. The stalled checkout was detected seconds ago—no more digging through spreadsheets.”
4. **Suspicious Checkout (10s)** – “Vision + RFID disagreed with POS for SKU PRD_X_HIGH. That’s Sandil’s enriched insight calling for manual review.”
5. **Inventory Snapshot (10s)** – “Back-end analysts get automatic shrinkage value reports; PRD_X_HIGH is an $4K risk flagged instantly.”

### Business Impact (1:20 – 1:45)
1. **Quantified Wins (10s)** – “Pilots show 40% reduction in queue wait-time variance and 60% shrinkage reduction on flagged items.”
2. **Workflow (10s)** – “Hesara streams detection, Dilusha pipes telemetry, Sandali closes the loop with the CX playbook you just saw.”
3. **Scalability (5s)** – “No external dependencies: pure Python backend, lightweight HTML dashboard, ready for rapid rollout.”

### Close (1:45 – 2:00)
1. **Call to Action (10s)** – “Imagine every store lead starting their shift with this command center. We’re ready to pilot across Sentinel locations next quarter.”
2. **Wrap (5s)** – “Thank you—happy to dive deeper into the analytics or integration stack.”

## Demo Checklist
- [ ] API server running (`python src/integration/api_server.py --seed-demo`).
- [ ] Dashboard open in browser at `src/dashboard/simple_dashboard.html`.
- [ ] Evidence/run demo script executed once to refresh artefacts.
- [ ] Timer visible to stay within 2 minutes.
