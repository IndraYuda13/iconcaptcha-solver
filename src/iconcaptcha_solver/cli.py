from __future__ import annotations

import argparse
import json
from pathlib import Path

from .solver import solve_iconcaptcha_data_url


def main() -> None:
    parser = argparse.ArgumentParser(prog="iconcaptcha-solver")
    parser.add_argument("input")
    parser.add_argument("--cell-count", type=int, default=5)
    parser.add_argument("--similarity-threshold", type=float, default=20.0)
    args = parser.parse_args()

    raw = args.input
    if raw.startswith("@"):
        raw = Path(raw[1:]).read_text().strip()
    elif Path(args.input).exists():
        raw = Path(args.input).read_text().strip()

    result = solve_iconcaptcha_data_url(
        raw,
        cell_count=args.cell_count,
        similarity_threshold=args.similarity_threshold,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
