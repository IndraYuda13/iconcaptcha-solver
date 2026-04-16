# iconcaptcha-solver

Reusable Python solver for IconCaptcha strips where the task is to click the icon shown the least number of times.

## What it does
- accepts a canvas data URL from a live IconCaptcha widget
- splits the strip into equal horizontal cells
- normalizes the image
- groups visually identical cells with mean absolute pixel distance
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
- If a target uses a different equal-width cell count, pass `cell_count=`.
