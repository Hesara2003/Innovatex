"""Multi-stream event correlation for Project Sentinel."""

from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Iterable, List, Optional, Tuple


def _parse_timestamp(value: Optional[str]) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _normalise_stream_name(stream: Optional[str]) -> str:
    if not stream:
        return "unknown"
    return str(stream).strip().lower()


def _deep_get(data: Dict[str, object], *keys: str) -> Optional[object]:
    current: object = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:  # type: ignore[unreachable]
            return None
        current = current[key]  # type: ignore[assignment]
    return current


class EventCorrelator:
    """Correlate RFID, POS, and computer-vision events within time windows."""

    def __init__(
        self,
        window_seconds: int = 30,
        max_history: int = 600,
    ) -> None:
        self.window = timedelta(seconds=max(1, window_seconds))
        self._events: Deque[Dict[str, object]] = deque()
        self._correlated: Deque[Dict[str, object]] = deque(maxlen=max_history)
        self._suspicious: Deque[Dict[str, object]] = deque(maxlen=max_history)
        self._seen_correlations: set[Tuple[str, str, str]] = set()
        self._seen_suspicious: set[Tuple[str, str, str]] = set()

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------
    def register_event(self, stream: str, event: Dict[str, object]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
        """Register a raw event and return new correlations and suspicious findings."""

        station_id = str(event.get("station_id", "UNKNOWN"))
        timestamp = _parse_timestamp(event.get("timestamp"))

        record = {
            "stream": _normalise_stream_name(stream or event.get("dataset")),
            "station_id": station_id,
            "timestamp": timestamp,
            "payload": event,
        }

        self._events.append(record)
        self._prune(timestamp)

        correlations, suspicious = self._evaluate_station(station_id)
        if correlations:
            self._correlated.extend(correlations)
        if suspicious:
            self._suspicious.extend(suspicious)

        return correlations, suspicious

    # ------------------------------------------------------------------
    # @algorithm MultiStreamCorrelation | Correlate RFID, POS, and vision data
    # ------------------------------------------------------------------
    def _evaluate_station(self, station_id: str) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
        recent_events = self._collect_recent_events(station_id)
        if not recent_events:
            return [], []

        groups = self._group_events(recent_events)
        new_correlated: List[Dict[str, object]] = []
        new_suspicious: List[Dict[str, object]] = []

        for pos_event in groups["pos"]:
            correlations, suspicious = self._assess_pos_event(
                station_id,
                pos_event,
                groups["rfid"],
                groups["vision"],
            )
            new_correlated.extend(correlations)
            new_suspicious.extend(suspicious)

        return new_correlated, new_suspicious

    def _collect_recent_events(self, station_id: str) -> List[Dict[str, object]]:
        if not self._events:
            return []
        current_time = self._events[-1]["timestamp"]
        window_start = current_time - self.window
        return [
            event
            for event in self._events
            if event["station_id"] == station_id and event["timestamp"] >= window_start
        ]

    def _group_events(self, events: Iterable[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
        buckets = {"rfid": [], "pos": [], "vision": []}
        rfid_streams = {"rfid", "rfid_data", "rfid_readings"}
        pos_streams = {"pos", "pos_transactions"}
        vision_streams = {"vision", "product_recognition", "product_recognism"}

        for event in events:
            stream = event["stream"]
            if stream in rfid_streams:
                buckets["rfid"].append(event)
            elif stream in pos_streams:
                buckets["pos"].append(event)
            elif stream in vision_streams:
                buckets["vision"].append(event)

        return buckets

    def _assess_pos_event(
        self,
        station_id: str,
        pos_event: Dict[str, object],
        rfid_events: Iterable[Dict[str, object]],
        vision_events: Iterable[Dict[str, object]],
    ) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
        sku = self._extract_sku(pos_event["payload"])
        if not sku:
            return [], []

        rfid_matches = [event for event in rfid_events if self._extract_sku(event["payload"]) == sku]
        vision_matches = [event for event in vision_events if self._extract_sku(event["payload"]) == sku]

        alignment = self._time_alignment(
            pos_event["timestamp"],
            [match["timestamp"] for match in rfid_matches + vision_matches],
        )
        confidence = self._confidence_score(bool(rfid_matches), bool(vision_matches), alignment)

        correlation = self._build_correlation(
            station_id,
            sku,
            pos_event,
            rfid_matches,
            vision_matches,
            confidence,
            alignment,
        )

        suspicious = self._build_suspicious(
            station_id,
            sku,
            pos_event,
            rfid_matches,
            vision_events,
            vision_matches,
            confidence,
        )

        return correlation, suspicious

    def _build_correlation(
        self,
        station_id: str,
        sku: str,
        pos_event: Dict[str, object],
        rfid_matches: List[Dict[str, object]],
        vision_matches: List[Dict[str, object]],
        confidence: float,
        alignment: float,
    ) -> List[Dict[str, object]]:
        key = (station_id, sku, pos_event["timestamp"].isoformat(timespec="seconds"))
        if confidence < 0.6 or key in self._seen_correlations:
            return []

        self._seen_correlations.add(key)
        return [
            {
                "event_type": "correlated_checkout",
                "station_id": station_id,
                "timestamp": pos_event["timestamp"].isoformat(),
                "confidence": round(confidence, 2),
                "sku": sku,
                "rfid_matches": len(rfid_matches),
                "vision_matches": len(vision_matches),
                "time_alignment": round(alignment, 2),
                "pos_payload": pos_event["payload"].get("data", pos_event["payload"]),
            }
        ]

    def _build_suspicious(
        self,
        station_id: str,
        sku: str,
        pos_event: Dict[str, object],
        rfid_matches: Iterable[Dict[str, object]],
        vision_events: Iterable[Dict[str, object]],
        vision_matches: Iterable[Dict[str, object]],
        confidence: float,
    ) -> List[Dict[str, object]]:
        reasons: List[str] = []
        rfid_matches = list(rfid_matches)
        vision_matches = list(vision_matches)
        vision_events = list(vision_events)
        if not rfid_matches:
            reasons.append("Missing RFID")
        if not vision_matches:
            reasons.append("Missing Vision")

        vision_predictions = set()
        for event in vision_events:
            candidate = self._extract_sku(event["payload"])
            if candidate:
                vision_predictions.add(candidate)

        rfid_skus = set()
        for event in rfid_matches:
            candidate = self._extract_sku(event["payload"])
            if candidate:
                rfid_skus.add(candidate)

        if vision_matches and sku not in vision_predictions:
            reasons.append("Vision mismatch")
        if rfid_matches and sku not in rfid_skus:
            reasons.append("RFID mismatch")
        if confidence < 0.5:
            reasons.append("Low confidence correlation")

        if not reasons:
            return []

        key = (station_id, sku, pos_event["timestamp"].isoformat(timespec="seconds"))
        if key in self._seen_suspicious:
            return []

        self._seen_suspicious.add(key)
        return [
            {
                "event_type": "suspicious_checkout",
                "station_id": station_id,
                "timestamp": pos_event["timestamp"].isoformat(),
                "sku": sku,
                "reasons": reasons,
                "confidence": round(confidence, 2),
                "pos_payload": pos_event["payload"].get("data", pos_event["payload"]),
            }
        ]

    # ------------------------------------------------------------------
    # Supporting algorithms and summaries
    # ------------------------------------------------------------------
    def _prune(self, current_time: datetime) -> None:
        window_start = current_time - self.window
        while self._events and self._events[0]["timestamp"] < window_start:
            self._events.popleft()

    def _extract_sku(self, payload: Dict[str, object]) -> Optional[str]:
        candidates = [
            _deep_get(payload, "data", "sku"),
            _deep_get(payload, "data", "predicted_product"),
            payload.get("sku"),
            payload.get("predicted_product"),
            payload.get("product_id"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None

    def _time_alignment(self, pivot: datetime, others: Iterable[datetime]) -> float:
        if not others:
            return 0.0
        min_diff = min(abs((pivot - other).total_seconds()) for other in others)
        max_window = max(self.window.total_seconds(), 1.0)
        return max(0.0, 1.0 - (min_diff / max_window))

    def _confidence_score(self, has_rfid: bool, has_vision: bool, alignment: float) -> float:
        score = 0.35  # POS foundation
        if has_rfid:
            score += 0.35
        if has_vision:
            score += 0.22
        score += min(0.08, alignment * 0.1)
        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Outputs for API/dashboard
    # ------------------------------------------------------------------
    def get_recent_correlations(self, limit: int = 10) -> List[Dict[str, object]]:
        return list(self._correlated)[-limit:]

    def get_recent_suspicious(self, limit: int = 10) -> List[Dict[str, object]]:
        return list(self._suspicious)[-limit:]

    def build_summary(self) -> Dict[str, object]:
        correlations = list(self._correlated)
        suspicious = list(self._suspicious)

        sku_counts = Counter(event["sku"] for event in correlations)
        suspicious_counts = Counter(event["station_id"] for event in suspicious)

        return {
            "window_seconds": int(self.window.total_seconds()),
            "recent_correlations": correlations[-10:],
            "recent_suspicious": suspicious[-10:],
            "top_correlated_skus": sku_counts.most_common(5),
            "stations_under_watch": suspicious_counts.most_common(5),
        }


event_correlator = EventCorrelator()