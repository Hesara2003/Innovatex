"""Dependency-free queue analytics for Project Sentinel."""

from __future__ import annotations

import math
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, Iterable, List, Optional


def _parse_timestamp(value: Optional[str]) -> datetime:
    """Best-effort ISO-8601 parsing with UTC fallback."""

    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.utcnow()


@dataclass
class QueueSnapshot:
    """Short-term queue observation used for analytics."""

    timestamp: datetime
    station_id: str
    customer_count: int = 0
    average_dwell_time: float = 0.0
    status: str = "active"
    service_rate: float = 0.0  # customers per minute
    delta_customers: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "station_id": self.station_id,
            "customer_count": self.customer_count,
            "average_dwell_time": self.average_dwell_time,
            "status": self.status,
            "service_rate": self.service_rate,
            "delta_customers": self.delta_customers,
            "notes": self.notes,
        }


class QueueMetricsService:
    """Provide queue health scoring, staffing and CX incident detection."""

    def __init__(
        self,
        target_customers_per_station: int = 6,
        history_length: int = 60,
        incident_history: int = 200,
    ) -> None:
        self.target_customers_per_station = max(1, target_customers_per_station)
        self._history: Dict[str, Deque[QueueSnapshot]] = defaultdict(
            lambda: deque(maxlen=history_length)
        )
        self.alert_history: Deque[Dict[str, object]] = deque(maxlen=incident_history)
        self._trend_window = min(history_length, 12)
        self._stagnation_threshold_minutes = 2.0

        self._thresholds = {
            "dwell_warning": 240,  # seconds
            "dwell_critical": 480,
            "queue_warning": self.target_customers_per_station + 2,
            "queue_critical": self.target_customers_per_station * 2,
        }

    # ------------------------------------------------------------------
    # Data ingestion
    # ------------------------------------------------------------------
    def ingest_observation(self, station_id: str, payload: Dict[str, object]) -> Dict[str, object]:
        """Store a queue observation and return updated health."""

        station_id = station_id or str(payload.get("station_id", "UNK"))
        timestamp = _parse_timestamp(payload.get("timestamp"))
        customer_count = int(payload.get("customer_count") or payload.get("customers", 0) or 0)
        dwell_time = float(payload.get("average_dwell_time") or payload.get("avg_wait", 0.0) or 0.0)
        status = str(payload.get("status", "active"))

        history = self._history[station_id]
        previous = history[-1] if history else None
        delta_customers = customer_count - (previous.customer_count if previous else customer_count)

        service_rate = payload.get("service_rate")
        if service_rate is None and previous is not None:
            elapsed_seconds = max((timestamp - previous.timestamp).total_seconds(), 1.0)
            serviced_customers = max(previous.customer_count - customer_count, 0)
            service_rate = serviced_customers * 60.0 / elapsed_seconds
        service_rate = float(service_rate or 0.0)

        snapshot = QueueSnapshot(
            timestamp=timestamp,
            station_id=station_id,
            customer_count=customer_count,
            average_dwell_time=dwell_time,
            status=status,
            service_rate=service_rate,
            delta_customers=delta_customers,
            notes=str(payload.get("notes", "")),
        )

        history.append(snapshot)

        incidents = self._detect_incidents(station_id)
        if incidents:
            self.alert_history.extend(incidents)

        return self.calculate_queue_health(station_id)

    # ------------------------------------------------------------------
    # @algorithm Queue Health Scoring | Calculates real-time queue efficiency
    # ------------------------------------------------------------------
    def calculate_queue_health(self, station_id: str) -> Dict[str, object]:
        history = self._history.get(station_id)
        if not history:
            return {
                "station_id": station_id,
                "health_score": 100.0,
                "status": "unknown",
                "alerts": [],
                "customer_count": 0,
                "average_dwell_time": 0.0,
                "service_rate": 0.0,
                "trend": 0.0,
                "volatility": 0.0,
                "timestamp": datetime.utcnow().isoformat(),
            }

        latest = history[-1]
        score = 100.0
        alerts: List[Dict[str, object]] = []

        if latest.average_dwell_time >= self._thresholds["dwell_critical"]:
            score -= 45
            alerts.append(
                {
                    "type": "dwell_time_critical",
                    "message": f"{station_id} wait {int(latest.average_dwell_time)}s exceeds SLA",
                    "priority": "high",
                }
            )
        elif latest.average_dwell_time >= self._thresholds["dwell_warning"]:
            score -= 25
            alerts.append(
                {
                    "type": "dwell_time_warning",
                    "message": f"{station_id} wait trending high ({int(latest.average_dwell_time)}s)",
                    "priority": "medium",
                }
            )

        if latest.customer_count >= self._thresholds["queue_critical"]:
            score -= 30
            alerts.append(
                {
                    "type": "queue_congestion",
                    "message": f"{station_id} queue critical ({latest.customer_count})",
                    "priority": "high",
                }
            )
        elif latest.customer_count >= self._thresholds["queue_warning"]:
            score -= 18
            alerts.append(
                {
                    "type": "queue_building",
                    "message": f"{station_id} queue building ({latest.customer_count})",
                    "priority": "medium",
                }
            )

        if latest.customer_count > 0 and latest.service_rate < 1.0:
            score -= 12
            alerts.append(
                {
                    "type": "service_rate_low",
                    "message": f"{station_id} serving {latest.service_rate:.1f}/min",
                    "priority": "medium",
                }
            )

        trend = self._calculate_trend(history)
        if trend > 0.35:
            score -= 8
            alerts.append(
                {
                    "type": "queue_growth",
                    "message": f"{station_id} queue growing {trend*100:.0f}%",
                    "priority": "medium",
                }
            )
        elif trend < -0.4:
            score += 3

        volatility = self._calculate_volatility(history)
        if volatility > 0.5:
            score -= 4

        score = max(0.0, min(score, 100.0))
        status = self._score_to_status(score)

        return {
            "station_id": station_id,
            "health_score": round(score, 1),
            "status": status,
            "alerts": alerts,
            "customer_count": latest.customer_count,
            "average_dwell_time": round(latest.average_dwell_time, 1),
            "service_rate": round(latest.service_rate, 2),
            "trend": round(trend, 3),
            "volatility": round(volatility, 3),
            "timestamp": latest.timestamp.isoformat(),
            "history": [snap.to_dict() for snap in list(history)[-5:]],
        }

    # ------------------------------------------------------------------
    # @algorithm Staff Allocation Optimizer | Recommends station management
    # ------------------------------------------------------------------
    def calculate_staff_allocation(self) -> Dict[str, object]:
        latest_snapshots = [history[-1] for history in self._history.values() if history]
        total_customers = sum(snap.customer_count for snap in latest_snapshots)
        active_stations = max(1, len(latest_snapshots))
        required_stations = max(1, math.ceil(total_customers / self.target_customers_per_station))

        if required_stations > active_stations:
            recommendation = f"Open {required_stations - active_stations} additional station(s)"
        elif required_stations < active_stations:
            recommendation = f"Idle {active_stations - required_stations} station(s) if demand stays low"
        else:
            recommendation = "Maintain current staffing"

        return {
            "recommendation": recommendation,
            "active_stations": active_stations,
            "required_stations": required_stations,
            "total_customers": total_customers,
            "target_per_station": self.target_customers_per_station,
            "efficiency_ratio": round(total_customers / active_stations, 2),
        }

    # ------------------------------------------------------------------
    # @algorithm CX Incident Detector | Identifies customer experience issues
    # ------------------------------------------------------------------
    def _detect_incidents(self, station_id: str) -> List[Dict[str, object]]:
        history = self._history.get(station_id)
        if not history or len(history) < 2:
            return []

        latest = history[-1]
        previous = history[-2]
        incidents: List[Dict[str, object]] = []

        if previous.customer_count > 0:
            surge_ratio = (latest.customer_count - previous.customer_count) / max(previous.customer_count, 1)
            if surge_ratio >= 0.6 and latest.customer_count >= self._thresholds["queue_warning"]:
                incidents.append(
                    self._build_incident(
                        station_id,
                        "queue_surge",
                        "Queue surge detected",
                        "high",
                        {
                            "from": previous.customer_count,
                            "to": latest.customer_count,
                            "ratio": round(surge_ratio, 2),
                        },
                    )
                )

        stagnation_minutes = self._stagnation_duration_minutes(history)
        if stagnation_minutes >= self._stagnation_threshold_minutes and latest.customer_count >= self._thresholds["queue_warning"]:
            incidents.append(
                self._build_incident(
                    station_id,
                    "stalled_checkout",
                    f"Queue stagnant for {stagnation_minutes:.1f} minutes",
                    "high",
                    {
                        "customer_count": latest.customer_count,
                        "service_rate": round(latest.service_rate, 2),
                    },
                )
            )

        if latest.customer_count == 0 and previous.customer_count >= self.target_customers_per_station:
            incidents.append(
                self._build_incident(
                    station_id,
                    "queue_cleared",
                    "Queue cleared suddenly",
                    "low",
                    {
                        "previous_customer_count": previous.customer_count,
                    },
                )
            )

        if latest.average_dwell_time >= self._thresholds["dwell_critical"]:
            incidents.append(
                self._build_incident(
                    station_id,
                    "extreme_wait",
                    "Extreme wait time recorded",
                    "critical",
                    {
                        "dwell_time": latest.average_dwell_time,
                    },
                )
            )

        return incidents

    def get_recent_incidents(self, limit: int = 20) -> List[Dict[str, object]]:
        return list(self.alert_history)[-limit:]

    # ------------------------------------------------------------------
    # Real-time dashboard data generator
    # ------------------------------------------------------------------
    def generate_dashboard_payload(self) -> Dict[str, object]:
        station_cards = [self.calculate_queue_health(station_id) for station_id in self._history]
        station_cards = [card for card in station_cards if card["status"] != "unknown"]

        overall_score = (
            sum(card["health_score"] for card in station_cards) / len(station_cards)
            if station_cards
            else 100.0
        )

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health_score": round(overall_score, 1),
            "stations": station_cards,
            "staffing": self.calculate_staff_allocation(),
            "incidents": self.get_recent_incidents(limit=10),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _score_to_status(self, score: float) -> str:
        if score >= 85:
            return "optimal"
        if score >= 70:
            return "stable"
        if score >= 50:
            return "at-risk"
        return "critical"

    def _calculate_trend(self, history: Iterable[QueueSnapshot]) -> float:
        snapshots = list(history)[-self._trend_window :]
        if len(snapshots) < 2:
            return 0.0

        start = snapshots[0].customer_count
        end = snapshots[-1].customer_count
        if start == 0 and end == 0:
            return 0.0
        if start == 0:
            return 1.0
        return (end - start) / start

    def _calculate_volatility(self, history: Iterable[QueueSnapshot]) -> float:
        snapshots = list(history)[-self._trend_window :]
        if len(snapshots) < 3:
            return 0.0
        counts = [snap.customer_count for snap in snapshots]
        mean = sum(counts) / len(counts)
        if mean == 0:
            return 0.0
        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        return min(1.0, variance ** 0.5 / mean)

    def _stagnation_duration_minutes(self, history: Iterable[QueueSnapshot]) -> float:
        snapshots = list(history)
        if len(snapshots) < 2:
            return 0.0

        stagnant = [snapshots[-1]]
        for snapshot in reversed(snapshots[:-1]):
            if snapshot.customer_count == stagnant[-1].customer_count:
                stagnant.append(snapshot)
            else:
                break

        if len(stagnant) < 2:
            return 0.0

        newest = stagnant[0]
        oldest = stagnant[-1]
        return max((newest.timestamp - oldest.timestamp).total_seconds() / 60.0, 0.0)

    def _build_incident(
        self,
        station_id: str,
        incident_type: str,
        message: str,
        priority: str,
        metadata: Optional[Dict[str, object]] = None,
    ) -> Dict[str, object]:
        return {
            "incident_id": uuid.uuid4().hex,
            "station_id": station_id,
            "type": incident_type,
            "message": message,
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }


queue_metrics_service = QueueMetricsService()