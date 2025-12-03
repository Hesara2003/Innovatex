#!/usr/bin/env python3
"""Project Sentinel - Demo Stream Client
Connects to the stream server and displays events in real-time.
"""
import socket
import json
import sys
from datetime import datetime

def connect_stream(host="localhost", port=8765):
    """Connect to stream server and display events."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            print(f"Connecting to stream server at {host}:{port}...")
            sock.connect((host, port))
            print("✓ Connected!")
            print("-" * 70)
            
            buffer = ""
            event_count = 0
            
            while True:
                data = sock.recv(4096).decode("utf-8")
                if not data:
                    break
                
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        try:
                            event = json.loads(line)
                            event_count += 1
                            
                            # Banner on first message
                            if event_count == 1 and event.get("service"):
                                print(f"Service: {event.get('service')}")
                                print(f"Datasets: {', '.join(event.get('datasets', []))}")
                                print(f"Events: {event.get('events')}")
                                print(f"Speed: {event.get('speed_factor')}x")
                                print("-" * 70)
                                continue
                            
                            # Regular events
                            dataset = event.get("dataset", "unknown")
                            seq = event.get("sequence", "?")
                            timestamp = event.get("timestamp", "")
                            
                            print(f"[{event_count-1:4d}] {dataset:20s} | seq:{seq:4d} | {timestamp}")
                            
                        except json.JSONDecodeError:
                            print(f"Warning: Invalid JSON: {line[:50]}")
            
            print(f"\nStream ended. Received {event_count} events total.")
            
    except ConnectionRefusedError:
        print(f"✗ Connection refused. Is the stream server running on {host}:{port}?")
        return 1
    except KeyboardInterrupt:
        print(f"\n\nStopped by user. Received {event_count} events.")
        return 0
    except Exception as e:
        print(f"✗ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    sys.exit(connect_stream(host, port))
