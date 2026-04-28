# IconCaptcha Solver Local HTTP API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local no-token HTTP API plus benchmark/corpus support to the pushed `iconcaptcha-solver` repo.

**Architecture:** Keep the existing Python solver as the canonical core. Add a FastAPI wrapper that converts JSON input into the existing solver call and maps the result into automation-friendly coordinate fields. Add benchmark fixtures as file-based JSONL so accuracy claims are data-backed and reproducible.

**Tech Stack:** Python 3.11+, Pillow, FastAPI, Uvicorn, unittest, urllib/request for black-box API tests.

---

## File Structure

- Modify `pyproject.toml`
  - Add FastAPI/Uvicorn dependencies.
  - Add `iconcaptcha-solver-api` console script.
- Create `src/iconcaptcha_solver/api.py`
  - Owns FastAPI app, request validation, response mapping, and CLI server entrypoint.
- Create `tests/test_api.py`
  - Unit tests against FastAPI `TestClient` for health, solve, and validation behavior.
- Modify `scripts/benchmark_fixtures.py`
  - Ensure live JSONL labels report sample count, success rate, threshold sweep, confidence buckets, and failed ids.
- Create `fixtures/live/images/.gitkeep`
  - Keeps corpus folder in repo.
- Create `fixtures/live/labels.example.jsonl`
  - Documents live label format without committing real private samples.
- Modify `README.md`
  - Document API run command, `/solve` request/response, no-token local-only warning, and benchmark workflow.

---

### Task 1: Add API package dependencies and entrypoint

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update package metadata**

Replace the dependencies and scripts sections with:

```toml
dependencies = [
  "Pillow>=10.0.0",
  "fastapi>=0.110.0",
  "uvicorn>=0.27.0",
]

[project.scripts]
iconcaptcha-solver = "iconcaptcha_solver.cli:main"
iconcaptcha-solver-api = "iconcaptcha_solver.api:main"
```

- [ ] **Step 2: Run metadata sanity check**

Run:
```bash
python3 -m py_compile src/iconcaptcha_solver/solver.py src/iconcaptcha_solver/cli.py
```

Expected: exits `0` with no output.

- [ ] **Step 3: Commit**

Run:
```bash
git add pyproject.toml
git commit -m "build: add API runtime entrypoint"
```

---

### Task 2: Write failing API tests

**Files:**
- Create: `tests/test_api.py`

- [ ] **Step 1: Add tests**

Create `tests/test_api.py` with:

```python
from __future__ import annotations

import base64
import io
import unittest

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from iconcaptcha_solver.api import app


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def _build_canvas_data_url(self) -> str:
        width = 320
        height = 50
        cell_width = width // 5
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for index in range(5):
            left = index * cell_width + 10
            right = (index + 1) * cell_width - 10
            top = 8
            bottom = height - 8
            if index == 3:
                draw.ellipse((left, top, right, bottom), fill=(40, 40, 40, 255))
            else:
                draw.rectangle((left, top, right, bottom), fill=(40, 40, 40, 255))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)
        self.assertEqual(response.json()["service"], "iconcaptcha-solver")

    def test_solve_accepts_canvas_data_url(self) -> None:
        response = self.client.post("/solve", json={"canvas_data_url": self._build_canvas_data_url()})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["success"], True)
        self.assertEqual(body["position"], 4)
        self.assertEqual(body["x"], body["centerX"])
        self.assertEqual(body["y"], body["centerY"])
        self.assertEqual(body["start"], 192)
        self.assertEqual(body["end"], 256)
        self.assertIn("confidence", body)
        self.assertNotIn("pairwise_mad", body)

    def test_solve_accepts_image_base64_with_debug(self) -> None:
        canvas = self._build_canvas_data_url()
        image_base64 = canvas.split(",", 1)[1]
        response = self.client.post(
            "/solve",
            json={"image_base64": image_base64, "return_debug": True},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["success"], True)
        self.assertEqual(body["position"], 4)
        self.assertIn("groups", body)
        self.assertIn("pairwise_mad", body)
        self.assertIn("distinctness", body)

    def test_solve_rejects_missing_image(self) -> None:
        response = self.client.post("/solve", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["success"], False)
        self.assertIn("exactly one", response.json()["error"])

    def test_solve_rejects_ambiguous_image(self) -> None:
        canvas = self._build_canvas_data_url()
        response = self.client.post(
            "/solve",
            json={"canvas_data_url": canvas, "image_base64": canvas.split(",", 1)[1]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["success"], False)
        self.assertIn("exactly one", response.json()["error"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure before implementation**

Run:
```bash
python3 -m unittest tests.test_api -v
```

Expected: FAIL because `iconcaptcha_solver.api` does not exist yet.

---

### Task 3: Implement FastAPI service

**Files:**
- Create: `src/iconcaptcha_solver/api.py`

- [ ] **Step 1: Add API implementation**

Create `src/iconcaptcha_solver/api.py` with:

```python
from __future__ import annotations

import argparse
import base64
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .solver import solve_iconcaptcha_data_url, solve_iconcaptcha_png_bytes

SERVICE_NAME = "iconcaptcha-solver"
SERVICE_VERSION = "0.1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8091

app = FastAPI(title=SERVICE_NAME, version=SERVICE_VERSION)


class SolveRequest(BaseModel):
    canvas_data_url: str | None = None
    image_base64: str | None = None
    cell_count: int = 5
    similarity_threshold: float = 20.0
    return_debug: bool = False


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.post("/solve")
def solve(request: SolveRequest) -> JSONResponse:
    try:
        result = _solve_request(request)
        return JSONResponse(_result_payload(result, return_debug=request.return_debug), status_code=200)
    except ValueError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)
    except Exception as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=500)


def _solve_request(request: SolveRequest):
    has_canvas = bool(request.canvas_data_url)
    has_image = bool(request.image_base64)
    if has_canvas == has_image:
        raise ValueError("exactly one of canvas_data_url or image_base64 is required")
    if request.cell_count < 2:
        raise ValueError("cell_count must be at least 2")
    if request.similarity_threshold <= 0:
        raise ValueError("similarity_threshold must be greater than 0")

    if request.canvas_data_url:
        return solve_iconcaptcha_data_url(
            request.canvas_data_url,
            cell_count=request.cell_count,
            similarity_threshold=request.similarity_threshold,
        )

    assert request.image_base64 is not None
    try:
        png_bytes = base64.b64decode(request.image_base64)
    except Exception as exc:
        raise ValueError("invalid image_base64") from exc
    return solve_iconcaptcha_png_bytes(
        png_bytes,
        cell_count=request.cell_count,
        similarity_threshold=request.similarity_threshold,
    )


def _result_payload(result, *, return_debug: bool) -> dict[str, Any]:
    cell_width = result.width // result.cell_count
    start = result.selected_cell_index * cell_width
    end = result.width if result.selected_cell_index == result.cell_count - 1 else (result.selected_cell_index + 1) * cell_width
    payload: dict[str, Any] = {
        "success": True,
        "position": result.selected_cell_number,
        "x": result.click_x,
        "y": result.click_y,
        "centerX": result.click_x,
        "centerY": result.click_y,
        "start": start,
        "end": end,
        "confidence": result.confidence,
        "cell_count": result.cell_count,
        "width": result.width,
        "height": result.height,
        "groups": result.groups,
    }
    if return_debug:
        payload["pairwise_mad"] = result.pairwise_mad
        payload["distinctness"] = result.distinctness
        payload["similarity_threshold"] = result.similarity_threshold
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(prog="iconcaptcha-solver-api")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    import uvicorn

    uvicorn.run("iconcaptcha_solver.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run focused API tests**

Run:
```bash
python3 -m unittest tests.test_api -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

Run:
```bash
git add src/iconcaptcha_solver/api.py tests/test_api.py
git commit -m "feat: add local iconcaptcha solve API"
```

---

### Task 4: Add live corpus skeleton and benchmark output support

**Files:**
- Modify: `scripts/benchmark_fixtures.py`
- Create: `fixtures/live/images/.gitkeep`
- Create: `fixtures/live/labels.example.jsonl`

- [ ] **Step 1: Inspect existing benchmark script**

Run:
```bash
sed -n '1,240p' scripts/benchmark_fixtures.py
```

Expected: existing script accepts JSONL and threshold list.

- [ ] **Step 2: Add example corpus files**

Create `fixtures/live/images/.gitkeep` as an empty file.

Create `fixtures/live/labels.example.jsonl` with:

```jsonl
{"id":"example-001","image":"images/example-001.png","predicted_position":4,"accepted":true,"target":"claimcoin","threshold":20.0,"notes":"example only, replace with real server verdict"}
```

- [ ] **Step 3: Ensure benchmark report includes required fields**

Modify `scripts/benchmark_fixtures.py` so its output includes:
- sample count
- accepted count
- success rate
- threshold sweep result
- confidence bucket stats
- failed sample ids

If the existing script already has some of these fields, preserve them and add only missing fields.

- [ ] **Step 4: Run benchmark smoke test**

Run:
```bash
PYTHONPATH=src python3 scripts/benchmark_fixtures.py fixtures/live/labels.example.jsonl --thresholds 16,20,24
```

Expected: exits cleanly or reports missing example image as a clear per-sample skip/error without traceback.

- [ ] **Step 5: Commit**

Run:
```bash
git add scripts/benchmark_fixtures.py fixtures/live/images/.gitkeep fixtures/live/labels.example.jsonl
git commit -m "feat: add iconcaptcha accuracy corpus workflow"
```

---

### Task 5: Document API and run full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README API docs**

Add sections for:
- local API install/run
- `/health`
- `/solve` request and response
- no-token local-only warning
- benchmark/corpus accuracy rule

Use this command example:

```bash
iconcaptcha-solver-api --host 127.0.0.1 --port 8091
```

Use this cURL example:

```bash
curl -s http://127.0.0.1:8091/health
```

- [ ] **Step 2: Run full test suite**

Run:
```bash
python3 -m unittest discover -s tests -v
```

Expected: all tests pass.

- [ ] **Step 3: Run API server smoke test**

Start server:
```bash
PYTHONPATH=src python3 -m iconcaptcha_solver.api --host 127.0.0.1 --port 8091
```

In another shell:
```bash
curl -s http://127.0.0.1:8091/health
```

Expected:
```json
{"ok":true,"service":"iconcaptcha-solver","version":"0.1.0"}
```

- [ ] **Step 4: Commit docs**

Run:
```bash
git add README.md
git commit -m "docs: document local iconcaptcha API"
```

---

### Task 6: Final repo hygiene and push

**Files:**
- Git metadata only.

- [ ] **Step 1: Check status**

Run:
```bash
git status --short
```

Expected: clean working tree.

- [ ] **Step 2: Push**

Run:
```bash
git push origin main
```

Expected: push succeeds to `IndraYuda13/iconcaptcha-solver`.

- [ ] **Step 3: Final report**

Report:
- commits created
- tests run and results
- API run command
- note that `>95%` is a target pending real labeled sample count, not yet a verified claim
