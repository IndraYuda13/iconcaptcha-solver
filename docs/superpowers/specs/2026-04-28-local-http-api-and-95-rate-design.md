# IconCaptcha Solver Local HTTP API and Accuracy Program Design

## Goal
Build the pushed `iconcaptcha-solver` repo into the canonical reusable solver service for future projects. The service should be easy to call from automation scripts and should return the click data needed to submit IconCaptcha challenges.

The accuracy goal is `>95%` success rate, but that number must only be claimed after measuring real labeled samples. Until then, the project reports measured rate from its corpus.

## Scope
In scope:
- Add a local HTTP API service to `iconcaptcha-solver`.
- Keep the existing library and CLI usable.
- Return API-compatible click coordinates and solver debug data.
- Add a corpus and benchmark workflow for live accepted/rejected samples.
- Prepare ClaimCoin to consume the API later, with local library fallback.

Out of scope for this first implementation:
- Public hosted service.
- Token/credit system.
- External database.
- ClaimCoin full integration unless requested as a follow-up step.

## API Design
Default bind:
- host: `127.0.0.1`
- port: `8091`
- no token/auth for now because this is local-only.

Endpoints:
- `GET /health`
- `POST /solve`

`GET /health` response:
```json
{
  "ok": true,
  "service": "iconcaptcha-solver",
  "version": "0.1.0"
}
```

`POST /solve` request supports either browser canvas data URL or raw image base64:
```json
{
  "canvas_data_url": "data:image/png;base64,...",
  "image_base64": null,
  "cell_count": 5,
  "similarity_threshold": 20.0,
  "return_debug": true
}
```

Validation rule:
- exactly one of `canvas_data_url` or `image_base64` should be present.
- `cell_count` defaults to `5`.
- `similarity_threshold` defaults to current solver default.
- `return_debug` defaults to `false` for lighter responses.

Successful response:
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
  "groups": [[0, 1, 2, 3], [4]],
  "pairwise_mad": null,
  "distinctness": null
}
```

Error response:
```json
{
  "success": false,
  "error": "invalid request"
}
```

Compatibility notes:
- `position`, `start`, `end`, `centerX`, and `centerY` mirror the useful shape seen in `antoniosousadev/iconcaptcha-solver`.
- `x` and `y` duplicate `centerX` and `centerY` for simple automation clients.
- Debug fields are included only when `return_debug=true`.

## Service Implementation
Recommended stack: FastAPI plus Uvicorn.

Reason:
- simple local JSON API
- automatic validation is useful
- easy to run as `python -m iconcaptcha_solver.api`
- easy future systemd unit

New files:
- `src/iconcaptcha_solver/api.py`
- `tests/test_api.py`

Packaging changes:
- add optional dependency group or normal dependencies for API runtime:
  - `fastapi`
  - `uvicorn`
- add console script:
  - `iconcaptcha-solver-api = iconcaptcha_solver.api:main`

Run command:
```bash
iconcaptcha-solver-api --host 127.0.0.1 --port 8091
```

## Accuracy and Corpus Program
The `>95%` target must be data-backed.

Add corpus layout:
```text
fixtures/live/
  images/
  labels.jsonl
```

Each label row:
```json
{
  "id": "20260428T120000Z-sample-001",
  "image": "images/sample-001.png",
  "predicted_position": 4,
  "accepted": true,
  "target": "claimcoin",
  "threshold": 20.0,
  "notes": "server verdict accepted"
}
```

Benchmark command should report:
- sample count
- accepted count
- success rate
- threshold sweep result
- confidence bucket stats
- failed sample ids

A `>95%` claim is allowed only when:
- sample count is at least 100 live labeled challenges, and
- success rate is at least 95%, and
- failures are preserved in corpus for regression.

## ClaimCoin Integration Plan
After API exists:
- update `claimcoin-autoclaim` config to prefer API endpoint:
  - `iconcaptcha_endpoint: http://127.0.0.1:8091/solve`
- keep current built-in solver fallback.
- do not remove built-in fallback until the external API has live runtime proof.

## Testing
Minimum tests:
- solver library tests still pass.
- CLI still returns JSON.
- API `/health` returns ok.
- API `/solve` accepts `canvas_data_url`.
- API `/solve` accepts `image_base64`.
- API returns useful validation error when input is missing or ambiguous.
- API response contains `position`, `x`, `y`, `centerX`, `centerY`, `start`, `end`, and `confidence`.

Verification command:
```bash
python3 -m unittest discover -s tests
```

## Risks
- Public API exposure without token is unsafe. Keep default bind `127.0.0.1`.
- A local API can be called too fast by bad loops. Optional rate limit can be added later if needed.
- `>95%` cannot be guaranteed by design alone. It must come from labeled live data.
- The external GitHub repo uses an opaque native binary, so it is useful as API-shape inspiration, not as trusted algorithm source.

## Approval State
Boskuu approved:
- local HTTP API
- no token for now
- focus on the pushed `IndraYuda13/iconcaptcha-solver` repo
- response should return click coordinates and submit-useful data
- accuracy work should target `>95%` using measured live samples
