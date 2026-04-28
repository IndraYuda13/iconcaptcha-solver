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
