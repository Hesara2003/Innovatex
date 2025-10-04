#!/usr/bin/env python3
"""Small TCP server that emits newline-delimited JSON for local testing.

Usage: python scripts/demo_server.py [host] [port] [count]
"""
import socket
import sys
import json
import time


def run(host: str = "127.0.0.1", port: int = 9999, count: int = 100):
    addr = (host, port)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(addr)
        srv.listen(1)
        print(f"demo server listening on {host}:{port}")
        conn, peer = srv.accept()
        with conn:
            print("client connected:", peer)
            for i in range(count):
                obj = {"ts": time.time(), "seq": i, "msg": f"event-{i}"}
                line = json.dumps(obj) + "\n"
                conn.sendall(line.encode("utf-8"))
                time.sleep(0.01)


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    run(host, port, count)
