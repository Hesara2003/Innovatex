import threading
import time
from src.io.stream_reader import read_stream


def start_demo_in_thread(host, port, count=20):
    import scripts.demo_server as srv

    t = threading.Thread(target=srv.run, args=(host, port, count), daemon=True)
    t.start()
    # give server a moment to bind
    time.sleep(0.1)
    return t


def test_read_stream_basic():
    host = "127.0.0.1"
    port = 9998
    t = start_demo_in_thread(host, port, count=10)
    it = read_stream(host, port, limit=5, timeout=2.0, reconnect=False)
    received = list(it)
    assert len(received) == 5
    for idx, item in enumerate(received):
        assert "seq" in item and item["seq"] == idx
