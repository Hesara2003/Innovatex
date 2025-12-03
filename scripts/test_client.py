#!/usr/bin/env python3
"""Test client for demo_server.py"""
import socket
import json
import sys

def test_client(host: str = "127.0.0.1", port: int = 9999):
    """Connect to demo server and receive JSON events."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            print(f"Connecting to {host}:{port}...")
            sock.connect((host, port))
            print("Connected! Receiving events...\n")
            
            # Receive data
            buffer = ""
            events_received = 0
            
            while True:
                data = sock.recv(1024).decode("utf-8")
                if not data:
                    break
                    
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        try:
                            event = json.loads(line)
                            events_received += 1
                            print(f"Event {events_received}: {event}")
                        except json.JSONDecodeError as e:
                            print(f"Error decoding: {e}")
            
            print(f"\nReceived {events_received} events total")
            return 0
            
    except ConnectionRefusedError:
        print(f"Connection refused. Is the server running on {host}:{port}?")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    sys.exit(test_client(host, port))
