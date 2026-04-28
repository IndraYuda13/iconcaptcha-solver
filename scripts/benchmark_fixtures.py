#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from iconcaptcha_solver.solver import solve_iconcaptcha_png_bytes


def parse_float_list(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(',') if x.strip()]


def load_rows(label_file: Path) -> list[dict]:
    if not label_file.exists():
        raise FileNotFoundError(f"labels file not found: {label_file}")
    rows: list[dict] = []
    for line in label_file.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        # Only passed samples provide a reliable correct cell oracle. Failed samples
        # are still useful for diagnostics but cannot prove the correct cell.
        if row.get('passed') and row.get('selected_cell_number'):
            rows.append(row)
    return rows


def run(labels: Path, thresholds: Iterable[float]) -> int:
    try:
        rows = load_rows(labels)
    except FileNotFoundError as exc:
        print(json.dumps({"status": 0, "message": str(exc), "labels": str(labels)}))
        return 2
    if not rows:
        print(json.dumps({"status": 0, "message": "no passed labeled rows found", "labels": str(labels)}))
        return 2

    root = labels.parent
    report = []
    for threshold in thresholds:
        ok = 0
        failures = []
        for row in rows:
            image_path = root / row['image']
            result = solve_iconcaptcha_png_bytes(image_path.read_bytes(), similarity_threshold=threshold)
            expected = int(row['selected_cell_number'])
            got = result.selected_cell_number
            if got == expected:
                ok += 1
            else:
                failures.append({
                    'image': row['image'],
                    'expected': expected,
                    'got': got,
                    'confidence': result.confidence,
                    'groups': result.groups,
                    'distinctness': result.distinctness,
                })
        report.append({
            'threshold': threshold,
            'total': len(rows),
            'correct': ok,
            'accuracy': round(ok / len(rows), 4),
            'failures': failures[:20],
        })

    print(json.dumps({'status': 1, 'labels': str(labels), 'samples': len(rows), 'report': report}, indent=2))
    best = max(report, key=lambda x: (x['accuracy'], -x['threshold']))
    return 0 if best['accuracy'] >= 0.9 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description='Benchmark IconCaptcha solver against captured live labels.jsonl')
    parser.add_argument('labels', type=Path, help='Path to labels.jsonl produced by xut_live_browser.py capture mode')
    parser.add_argument('--thresholds', default='8,12,16,20,24,28')
    args = parser.parse_args()
    return run(args.labels, parse_float_list(args.thresholds))


if __name__ == '__main__':
    raise SystemExit(main())
