from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.pipeline import transform


def test_normalize_pos_payload():
    payload = {
        "timestamp": "2025-08-13T16:08:40",
        "station_id": "SCC1",
        "status": "Active",
        "data": {
            "customer_id": "C056",
            "sku": "PRD_F_14",
            "product_name": "Nestomalt (400g)",
            "barcode": "4792024011348",
            "price": 540.0,
            "weight_g": 400.0,
        },
    }

    record = transform.normalize_payload("POS_Transactions", payload)

    assert record.dataset == "pos_transactions"
    assert record.sku == "PRD_F_14"
    assert record.customer_id == "C056"
    assert record.attributes["product_name"] == "Nestomalt (400g)"
    assert record.timestamp == datetime.fromisoformat("2025-08-13T16:08:40")
    assert record.metadata["source_dataset"] == "POS_Transactions"


def test_iter_jsonl_records(tmp_path):
    sample = {
        "timestamp": "2025-08-13T16:08:40",
        "station_id": "SCC1",
        "status": "Active",
        "data": {"predicted_product": "PRD_F_14", "accuracy": 0.9},
    }
    path = tmp_path / "product_recognition.jsonl"
    path.write_text(json.dumps(sample) + "\n\n", encoding="utf-8")

    records = list(transform.iter_jsonl_records(path))

    assert len(records) == 1
    record = records[0]
    assert record.dataset == "product_recognition"
    assert record.sku == "PRD_F_14"
    assert record.attributes["accuracy"] == 0.9


def test_normalize_stream_frame_preserves_metadata():
    payload = {
        "timestamp": "2025-08-13T16:08:40",
        "station_id": "SCC1",
        "status": "Active",
        "data": {"customer_id": "C056", "sku": "PRD_F_14"},
    }
    frame = {
        "dataset": "POS_Transactions",
        "event": payload,
        "sequence": 42,
        "timestamp": "2025-08-13T16:08:41",
        "original_timestamp": payload["timestamp"],
    }

    record = transform.normalize_stream_frame(frame)

    assert record.metadata["source_dataset"] == "POS_Transactions"
    assert record.metadata["sequence"] == 42
    assert record.metadata["original_timestamp"] == "2025-08-13T16:08:40"


def test_normalized_record_to_dict_controls_metadata():
    record = transform.NormalizedRecord(
        dataset="rfid_readings",
        timestamp=datetime.fromisoformat("2025-08-13T16:00:00"),
        station_id=None,
        status="Active",
        sku="PRD_F_01",
        customer_id=None,
        attributes={"epc": None, "location": "SCC1"},
        metadata={"sequence": 10},
    )

    as_dict = record.to_dict()
    assert "station_id" not in as_dict
    assert as_dict["attributes"] == {"location": "SCC1"}
    assert "metadata" not in as_dict

    as_dict_with_meta = record.to_dict(include_metadata=True)
    assert as_dict_with_meta["metadata"] == {"sequence": 10}


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("POS_Transactions", "pos_transactions"),
        ("Product_recognism", "product_recognition"),
        ("Queue_monitor", "queue_monitoring"),
        ("RFID_data", "rfid_readings"),
    ],
)
def test_canonical_dataset_aliases(alias, expected):
    assert transform.canonical_dataset(alias) == expected


def test_canonical_dataset_unknown_alias():
    with pytest.raises(ValueError):
        transform.canonical_dataset("unknown_dataset")


def test_load_datasets_reads_selected(tmp_path):
    data = {
        "timestamp": "2025-08-13T16:00:00",
        "station_id": "SCC1",
        "status": "Active",
        "data": {"customer_id": "C001", "sku": "PRD_F_01"},
    }
    (tmp_path / "pos_transactions.jsonl").write_text(json.dumps(data) + "\n", encoding="utf-8")

    records = transform.load_datasets(tmp_path, datasets=["pos_transactions"])

    assert len(records) == 1
    record = records[0]
    assert record.dataset == "pos_transactions"
    assert record.sku == "PRD_F_01"
    assert record.customer_id == "C001"
