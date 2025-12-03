#!/usr/bin/env python3
"""Test API endpoints"""
import urllib.request
import json

def test_endpoint(endpoint, name):
    try:
        url = f"http://localhost:5000{endpoint}"
        response = urllib.request.urlopen(url)
        data = json.loads(response.read())
        print(f"✓ {name} endpoint working")
        return data
    except Exception as e:
        print(f"✗ {name} endpoint failed: {e}")
        return None

# Test dashboard
print("Testing API Endpoints...")
print("-" * 50)

dashboard = test_endpoint("/api/dashboard", "Dashboard")
if dashboard:
    print(f"  System Status: {dashboard.get('system_status')}")
    print(f"  Timestamp: {dashboard.get('timestamp')}")
    queue = dashboard.get('queue', {})
    print(f"  Queue stations: {len(queue.get('stations', []))}")

print()

alerts = test_endpoint("/api/alerts", "Alerts")
if alerts:
    print(f"  Detection events: {len(alerts.get('detection_events', []))}")
    print(f"  Queue incidents: {len(alerts.get('queue_incidents', []))}")
    print(f"  Suspicious checkouts: {len(alerts.get('suspicious_checkouts', []))}")

print()

queue_health = test_endpoint("/api/queue-health", "Queue Health")
if queue_health:
    print(f"  Overall score: {queue_health.get('overall_score', 'N/A')}")

print()

correlations = test_endpoint("/api/correlations", "Correlations")
if correlations:
    print(f"  Active transactions: {correlations.get('active_transactions', 'N/A')}")

print("\n" + "=" * 50)
print("API Server Test Complete!")
