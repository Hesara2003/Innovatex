import socket
from typing import Iterator

# @algorithm Stream Reader | Normalize TCP JSONL lines to dicts

def read_stream(host: str, port: int, limit: int | None = None) -> Iterator[bytes]:
    """
    Connect to the TCP server and yield raw newline-delimited bytes.
    Parsing to dict is left to higher layers to keep IO fast.
    """
    addr = (host, port)
    remaining = limit
    with socket.create_connection(addr, timeout=10) as s:
        buf = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    yield line
                    if remaining is not None:
                        remaining -= 1
                        if remaining <= 0:
                            return
