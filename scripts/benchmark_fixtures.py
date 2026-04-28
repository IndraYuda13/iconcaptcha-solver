#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Iterable

from iconcaptcha_solver.solver import solve_iconcaptcha_png_bytes


def parse_float_list(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(',') if x.strip()]


def load_rows(label_file: Path) -> list[dict]:
    if not label_file.exists():
        raise FileNotFoundError(f"labels file not found: {label_file}")
    rows: list[dict] = []
    for line_number, line in enumerate(label_file.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        row.setdefault('id', f'line-{line_number}')
        rows.append(row)
    return rows


def _expected_position(row: dict) -> int | None:
    if row.get('selected_cell_number'):
        return int(row['selected_cell_number'])
    if row.get('expected_position'):
        return int(row['expected_position'])
    if row.get('accepted') is True and row.get('predicted_position'):
        return int(row['predicted_position'])
    if row.get('passed') is True and row.get('predicted_position'):
        return int(row['predicted_position'])
    return None


def _bucket(confidence: float) -> str:
    if confidence >= 0.9:
        return '0.90-1.00'
    if confidence >= 0.75:
        return '0.75-0.89'
    if confidence >= 0.6:
        return '0.60-0.74'
    return '0.00-0.59'


def run(labels: Path, thresholds: Iterable[float]) -> int:
    try:
        rows = load_rows(labels)
    except FileNotFoundError as exc:
        print(json.dumps({"status": 0, "message": str(exc), "labels": str(labels)}))
        return 2
    if not rows:
        print(json.dumps({"status": 0, "message": "no labeled rows found", "labels": str(labels)}))
        return 2

    root = labels.parent
    report = []
    usable_rows = [row for row in rows if _expected_position(row) is not None]
    accepted_count = sum(1 for row in rows if row.get('accepted') is True or row.get('passed') is True)
    skipped_rows = [row.get('id') for row in rows if _expected_position(row) is None]

    for threshold in thresholds:
        correct = 0
        failures = []
        errors = []
        confidences: list[float] = []
        confidence_buckets: dict[str, dict[str, int]] = {}
        for row in usable_rows:
            expected = _expected_position(row)
            assert expected is not None
            image_path = root / row['image']
            if not image_path.exists():
                errors.append({'id': row.get('id'), 'image': row.get('image'), 'error': 'image file not found'})
                continue
            try:
                result = solve_iconcaptcha_png_bytes(image_path.read_bytes(), similarity_threshold=threshold)
            except Exception as exc:
                errors.append({'id': row.get('id'), 'image': row.get('image'), 'error': str(exc)})
                continue
            got = result.selected_cell_number
            confidences.append(result.confidence)
            bucket = _bucket(result.confidence)
            confidence_buckets.setdefault(bucket, {'total': 0, 'correct': 0})
            confidence_buckets[bucket]['total'] += 1
            if got == expected:
                correct += 1
                confidence_buckets[bucket]['correct'] += 1
            else:
                failures.append({
                    'id': row.get('id'),
                    'image': row['image'],
                    'expected': expected,
                    'got': got,
                    'confidence': result.confidence,
                    'groups': result.groups,
                    'distinctness': result.distinctness,
                })
        evaluated = len(usable_rows) - len(errors)
        report.append({
            'threshold': threshold,
            'sample_count': len(rows),
            'usable_count': len(usable_rows),
            'evaluated_count': evaluated,
            'accepted_count': accepted_count,
            'correct_count': correct,
            'success_rate': round(correct / evaluated, 4) if evaluated else 0.0,
            'average_confidence': round(mean(confidences), 4) if confidences else 0.0,
            'confidence_buckets': confidence_buckets,
            'failed_sample_ids': [item['id'] for item in failures[:50]],
            'failures': failures[:20],
            'errors': errors[:20],
            'skipped_unlabeled_ids': skipped_rows[:50],
        })

    best = max(report, key=lambda x: (x['success_rate'], -x['threshold']))
    output = {
        'status': 1 if best['evaluated_count'] else 0,
        'labels': str(labels),
        'sample_count': len(rows),
        'accepted_count': accepted_count,
        'threshold_sweep': report,
        'best_threshold': best['threshold'],
        'best_success_rate': best['success_rate'],
        'claim_ready_95pct': best['evaluated_count'] >= 100 and best['success_rate'] >= 0.95,
    }
    print(json.dumps(output, indent=2))
    if not best['evaluated_count']:
        return 2
    return 0 if best['success_rate'] >= 0.9 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description='Benchmark IconCaptcha solver against captured live labels.jsonl')
    parser.add_argument('labels', type=Path, help='Path to live labels.jsonl')
    parser.add_argument('--thresholds', default='8,12,16,20,24,28')
    args = parser.parse_args()
    return run(args.labels, parse_float_list(args.thresholds))


if __name__ == '__main__':
    raise SystemExit(main())
