# Utilities to normalize incoming JSONL payloads (placeholder)

def normalize_event(raw_line: bytes) -> dict:
    return {"raw": raw_line.decode("utf-8", errors="ignore")}
