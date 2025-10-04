import socket
import json
import time
import logging
from typing import Iterator, Dict, Optional

logger = logging.getLogger(__name__)


def read_stream(
    host: str,
    port: int,
    limit: Optional[int] = None,
    timeout: float = 10.0,
    reconnect: bool = True,
    max_retries: int = 5,
    backoff_factor: float = 0.5,
    strict: bool = False,
) -> Iterator[Dict]:
    """Connect to a TCP server that emits newline-delimited JSON and yield parsed dicts.

    Behaviour and parameters:
    - host/port: address of the TCP JSONL server.
    - limit: optional max number of messages to yield (None = unlimited).
    - timeout: socket connect/recv timeout in seconds.
    - reconnect: whether to try reconnecting on failure.
    - max_retries: maximum reconnect attempts (when reconnect=True).
    - backoff_factor: base backoff (exponential backoff is used).
    - strict: if True, raise on decoding/parsing errors; otherwise skip malformed lines.

    Yields:
        dict objects parsed from each JSON line.

    Errors:
        Raises ConnectionError when connection cannot be established or retries exhausted.
    """

    addr = (host, port)
    remaining = limit
    attempts = 0

    while True:
        try:
            attempts += 1
            with socket.create_connection(addr, timeout=timeout) as s:
                s.settimeout(timeout)
                buf = b""
                logger.debug("connected to %s:%s", host, port)
                while True:
                    try:
                        chunk = s.recv(4096)
                    except socket.timeout:
                        # treat timeout as transient; continue reading
                        logger.debug("recv timeout, continuing")
                        continue
                    if not chunk:
                        logger.debug("connection closed by peer")
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            text = line.decode("utf-8")
                        except UnicodeDecodeError as e:
                            logger.warning("failed to decode line as utf-8: %s", e)
                            if strict:
                                raise
                            continue
                        try:
                            obj = json.loads(text)
                        except Exception as e:
                            logger.warning("failed to parse json line: %s", e)
                            if strict:
                                raise
                            continue
                        yield obj
                        if remaining is not None:
                            remaining -= 1
                            if remaining <= 0:
                                return
            # if we exit the `with` block, connection closed cleanly - decide to reconnect or stop
            if not reconnect:
                return
            # reset attempts after a successful connection loop exit
            attempts = 0
        except Exception as exc:  # socket errors, connection refused, etc.
            logger.debug("connection attempt failed: %s", exc)
            if not reconnect:
                raise ConnectionError(f"failed to connect to {addr}: {exc}") from exc
            if attempts > max_retries:
                raise ConnectionError(f"max reconnect attempts exceeded for {addr}") from exc
            backoff = backoff_factor * (2 ** (attempts - 1))
            logger.info("retrying connection to %s:%s in %.2fs (%s)", host, port, backoff, exc)
            time.sleep(backoff)
