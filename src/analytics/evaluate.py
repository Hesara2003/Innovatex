"""Evaluation utilities for Project Sentinel event pipelines."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


Key = Tuple[str, ...]


@dataclass(frozen=True)
class EvaluationResult:
    precision: float
    recall: float
    f1: float
    support: int
    true_positives: List[Key]
    false_positives: List[Key]
    false_negatives: List[Key]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "support": self.support,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


def load_jsonl(path: Path) -> List[Mapping[str, Any]]:
    """Load newline-delimited JSON records from *path*."""

    records: List[Mapping[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _dig(record: Mapping[str, Any], field: str) -> Any:
    current: Any = record
    for part in field.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            return None
    return current


def _make_key(record: Mapping[str, Any], fields: Sequence[str], *, drop_missing: bool) -> Optional[Key]:
    parts: List[str] = []
    for field in fields:
        value = _dig(record, field)
        if value is None:
            if drop_missing:
                return None
            parts.append("__MISSING__")
        else:
            parts.append(str(value))
    return tuple(parts)


def _unique_keys(records: Iterable[Mapping[str, Any]], fields: Sequence[str], *, drop_missing: bool) -> List[Key]:
    keys: List[Key] = []
    seen: set[Key] = set()
    for record in records:
        key = _make_key(record, fields, drop_missing=drop_missing)
        if key is None or key in seen:
            continue
        keys.append(key)
        seen.add(key)
    return keys


def _safe_div(num: float, denom: float) -> float:
    return num / denom if denom else 0.0


def evaluate_records(
    predictions: Iterable[Mapping[str, Any]],
    references: Iterable[Mapping[str, Any]],
    fields: Sequence[str],
    *,
    drop_missing: bool = True,
) -> EvaluationResult:
    """Compute precision/recall metrics using the selected *fields* as key."""

    pred_keys = set(_unique_keys(predictions, fields, drop_missing=drop_missing))
    ref_keys = set(_unique_keys(references, fields, drop_missing=drop_missing))

    tp = sorted(pred_keys & ref_keys)
    fp = sorted(pred_keys - ref_keys)
    fn = sorted(ref_keys - pred_keys)

    precision = _safe_div(len(tp), len(tp) + len(fp))
    recall = _safe_div(len(tp), len(tp) + len(fn))
    f1 = _safe_div(2 * precision * recall, precision + recall) if (precision + recall) else 0.0

    return EvaluationResult(
        precision=precision,
        recall=recall,
        f1=f1,
        support=len(ref_keys),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
    )


def evaluate_files(
    predictions_path: Path,
    references_path: Path,
    fields: Sequence[str],
    *,
    drop_missing: bool = True,
) -> EvaluationResult:
    preds = load_jsonl(predictions_path)
    refs = load_jsonl(references_path)
    return evaluate_records(preds, refs, fields, drop_missing=drop_missing)


def _format_key(key: Key, fields: Sequence[str]) -> str:
    return ", ".join(f"{field}={value}" for field, value in zip(fields, key))


def format_report(result: EvaluationResult, fields: Sequence[str]) -> str:
    """Build a human-readable report string for *result*."""

    lines = [
        f"precision: {result.precision:.3f}",
        f"recall   : {result.recall:.3f}",
        f"f1       : {result.f1:.3f}",
        f"support  : {result.support}",
    ]

    if result.false_positives:
        lines.append("false positives:")
        lines.extend(f"  - {_format_key(key, fields)}" for key in result.false_positives)
    if result.false_negatives:
        lines.append("false negatives:")
        lines.extend(f"  - {_format_key(key, fields)}" for key in result.false_negatives)
    if result.true_positives:
        lines.append("true positives:")
        lines.extend(f"  - {_format_key(key, fields)}" for key in result.true_positives)

    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate pipeline outputs against a reference taxonomy")
    parser.add_argument("--predictions", "-p", type=Path, required=True, help="Path to produced JSONL events")
    parser.add_argument("--reference", "-r", type=Path, required=True, help="Reference JSONL with labeled events")
    parser.add_argument(
        "--fields",
        "-f",
        nargs="+",
        default=["dataset", "attributes.event_name"],
        help="Field(s) used to construct the comparison key (dot notation supported)",
    )
    parser.add_argument(
        "--keep-missing",
        action="store_true",
        help="Keep records with missing fields in the evaluation",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    drop_missing = not args.keep_missing
    result = evaluate_files(args.predictions, args.reference, args.fields, drop_missing=drop_missing)
    print(format_report(result, args.fields))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
