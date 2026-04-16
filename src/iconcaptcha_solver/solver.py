from __future__ import annotations

import base64
import io
from dataclasses import asdict, dataclass
from statistics import mean

from PIL import Image, ImageOps


@dataclass(slots=True)
class IconCaptchaSolveResult:
    cell_count: int
    selected_cell_index: int
    selected_cell_number: int
    click_x: int
    click_y: int
    similarity_threshold: float
    groups: list[list[int]]
    pairwise_mad: list[list[float]]
    distinctness: list[float]
    confidence: float
    width: int
    height: int

    def to_dict(self) -> dict:
        return asdict(self)


def solve_iconcaptcha_data_url(
    canvas_data_url: str,
    *,
    cell_count: int = 5,
    similarity_threshold: float = 5.0,
) -> IconCaptchaSolveResult:
    if not canvas_data_url or "," not in canvas_data_url:
        raise ValueError("iconcaptcha canvas data URL is empty")
    _, payload = canvas_data_url.split(",", 1)
    try:
        png_bytes = base64.b64decode(payload)
    except Exception as exc:
        raise ValueError("invalid iconcaptcha canvas data URL") from exc
    return solve_iconcaptcha_png_bytes(
        png_bytes,
        cell_count=cell_count,
        similarity_threshold=similarity_threshold,
    )


def solve_iconcaptcha_png_bytes(
    png_bytes: bytes,
    *,
    cell_count: int = 5,
    similarity_threshold: float = 5.0,
) -> IconCaptchaSolveResult:
    if cell_count < 2:
        raise ValueError("cell_count must be at least 2")

    image = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    normalized = _normalize_canvas(image)
    width, height = normalized.size
    cell_width = width // cell_count
    if cell_width < 1:
        raise ValueError("canvas is too small")

    cell_vectors: list[list[int]] = []
    for index in range(cell_count):
        left = index * cell_width
        right = width if index == cell_count - 1 else (index + 1) * cell_width
        cell = normalized.crop((left, 0, right, height))
        cell = _trim_cell(cell)
        cell = cell.resize((32, 32))
        cell_vectors.append(list(cell.getdata()))

    pairwise = _build_pairwise_mad(cell_vectors)
    groups = _group_cells(pairwise, similarity_threshold)
    distinctness = [round(mean([value for j, value in enumerate(row) if j != i]), 4) for i, row in enumerate(pairwise)]

    min_group_size = min(len(group) for group in groups)
    candidate_groups = [group for group in groups if len(group) == min_group_size]
    chosen_group = max(candidate_groups, key=lambda group: (_group_distinctness(group, distinctness), -group[0]))
    selected_index = max(chosen_group, key=lambda idx: (distinctness[idx], -idx))

    confidence = _estimate_confidence(groups, distinctness, selected_index)
    click_x = int((selected_index + 0.5) * cell_width)
    click_y = int(height / 2)

    return IconCaptchaSolveResult(
        cell_count=cell_count,
        selected_cell_index=selected_index,
        selected_cell_number=selected_index + 1,
        click_x=click_x,
        click_y=click_y,
        similarity_threshold=similarity_threshold,
        groups=groups,
        pairwise_mad=[[round(value, 4) for value in row] for row in pairwise],
        distinctness=distinctness,
        confidence=confidence,
        width=width,
        height=height,
    )


def _normalize_canvas(image: Image.Image) -> Image.Image:
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    background.alpha_composite(image)
    gray = ImageOps.grayscale(background)
    return ImageOps.autocontrast(gray)


def _trim_cell(image: Image.Image) -> Image.Image:
    if image.width <= 4 or image.height <= 4:
        return image
    return image.crop((2, 2, image.width - 2, image.height - 2))


def _build_pairwise_mad(cell_vectors: list[list[int]]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for left in cell_vectors:
        row: list[float] = []
        for right in cell_vectors:
            row.append(sum(abs(a - b) for a, b in zip(left, right)) / len(left))
        matrix.append(row)
    return matrix


def _group_cells(pairwise: list[list[float]], threshold: float) -> list[list[int]]:
    groups: list[list[int]] = []
    for index in range(len(pairwise)):
        placed = False
        for group in groups:
            reference_distance = min(pairwise[index][member] for member in group)
            if reference_distance <= threshold:
                group.append(index)
                placed = True
                break
        if not placed:
            groups.append([index])
    return groups


def _group_distinctness(group: list[int], distinctness: list[float]) -> float:
    return mean(distinctness[index] for index in group)


def _estimate_confidence(groups: list[list[int]], distinctness: list[float], selected_index: int) -> float:
    selected_group_size = next(len(group) for group in groups if selected_index in group)
    best = distinctness[selected_index]
    others = [value for index, value in enumerate(distinctness) if index != selected_index]
    gap = best - max(others) if others else best
    score = 0.45
    if selected_group_size == 1:
        score += 0.25
    score += max(0.0, min(0.3, gap / 25.0))
    return round(max(0.0, min(0.99, score)), 4)
