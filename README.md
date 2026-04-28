# iconcaptcha-solver

Reusable Python solver for IconCaptcha strips where the task is to click the icon shown the least number of times.

## What it does
- accepts a canvas data URL from a live IconCaptcha widget
- splits the strip into equal horizontal cells
- normalizes the image
- groups visually identical cells with shift-aware mean absolute pixel distance so small left/right offsets do not look like different icons
- returns the least-repeated cell plus click coordinates

## Why this exists
This solver was extracted from a live ClaimCoin withdraw workflow after repeated real widget solves succeeded with the same heuristic.

## Install
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
```

## CLI
```bash
iconcaptcha-solver @canvas-data-url.txt
```

Or directly with Python:
```bash
PYTHONPATH=src python3 -m iconcaptcha_solver.cli @canvas-data-url.txt
```

## Local HTTP API
Run the local no-token API on loopback only:

```bash
iconcaptcha-solver-api --host 127.0.0.1 --port 8091
```

Development form:

```bash
PYTHONPATH=src python3 -m iconcaptcha_solver.api --host 127.0.0.1 --port 8091
```

Health check:

```bash
curl -s http://127.0.0.1:8091/health
```

Expected response:

```json
{"ok":true,"service":"iconcaptcha-solver","version":"0.1.0"}
```

Solve request with a browser canvas data URL:

```bash
curl -s http://127.0.0.1:8091/solve \
  -H 'Content-Type: application/json' \
  -d '{
    "canvas_data_url": "data:image/png;base64,...",
    "cell_count": 5,
    "similarity_threshold": 20.0,
    "return_debug": false
  }'
```

Solve request with raw PNG base64:

```json
{
  "image_base64": "BASE64_PNG",
  "cell_count": 5,
  "similarity_threshold": 20.0,
  "return_debug": true
}
```

Response shape:

```json
{
  "success": true,
  "position": 4,
  "x": 224,
  "y": 25,
  "centerX": 224,
  "centerY": 25,
  "start": 192,
  "end": 256,
  "confidence": 0.91,
  "cell_count": 5,
  "width": 320,
  "height": 50,
  "groups": [[0, 1, 2, 3], [4]]
}
```

Security note: this API has no token by design for now. Keep it bound to `127.0.0.1` unless a separate auth layer is added.

## Library usage
```python
from iconcaptcha_solver.solver import solve_iconcaptcha_data_url

result = solve_iconcaptcha_data_url(canvas_data_url)
print(result.selected_cell_number, result.click_x, result.click_y)
```

## Output shape
The solver returns:
- `selected_cell_index` and `selected_cell_number`
- click coordinates `click_x` and `click_y`
- grouping details under `groups`
- pairwise distance matrix under `pairwise_mad`
- rough `confidence`

## Notes
- Default assumption is a 5-cell horizontal strip because that is the live ClaimCoin withdraw shape that was proven.
- The default similarity threshold is tuned for the shift-aware matcher. If a target uses a different equal-width cell count, pass `cell_count=`.

## Live fixture benchmark
Captured live fixtures can be benchmarked before changing solver thresholds:

```bash
PYTHONPATH=src python3 scripts/benchmark_fixtures.py fixtures/live/labels.jsonl \
  --thresholds 8,12,16,20,24,28
```

Corpus layout:

```text
fixtures/live/
  images/
  labels.jsonl
```

Label row shape:

```json
{"id":"sample-001","image":"images/sample-001.png","predicted_position":4,"accepted":true,"target":"claimcoin","threshold":20.0,"notes":"server verdict accepted"}
```

The benchmark reports sample count, accepted count, threshold sweep, success rate, confidence buckets, failed ids, and image-loading errors. Do not claim `>95%` until at least 100 live labeled challenges are preserved and the measured success rate is at least 95%.
