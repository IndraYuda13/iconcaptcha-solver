from __future__ import annotations

import base64
import io
import unittest

from PIL import Image, ImageDraw

from iconcaptcha_solver.solver import solve_iconcaptcha_data_url


class SolverTests(unittest.TestCase):
    def _build_canvas(self, labels: list[str | tuple[str, int]], fill: tuple[int, int, int, int] = (40, 40, 40, 255)) -> str:
        width = 320
        height = 50
        cell_width = width // len(labels)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for index, item in enumerate(labels):
            if isinstance(item, tuple):
                label, offset_x = item
            else:
                label, offset_x = item, 0
            left = index * cell_width + 10 + offset_x
            right = (index + 1) * cell_width - 10 + offset_x
            top = 8
            bottom = height - 8
            if label == "square":
                draw.rectangle((left, top, right, bottom), fill=fill)
            elif label == "circle":
                draw.ellipse((left, top, right, bottom), fill=fill)
            elif label == "triangle":
                draw.polygon(
                    [(left + (right - left) / 2, top), (right, bottom), (left, bottom)],
                    fill=fill,
                )
            else:
                raise ValueError(label)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

    def test_unique_against_four_same(self) -> None:
        result = solve_iconcaptcha_data_url(self._build_canvas(["circle", "square", "square", "square", "square"]))
        self.assertEqual(result.selected_cell_number, 1)

    def test_unique_in_two_two_one(self) -> None:
        result = solve_iconcaptcha_data_url(self._build_canvas(["square", "circle", "circle", "triangle", "triangle"]))
        self.assertEqual(result.selected_cell_number, 1)
        self.assertEqual(sorted(len(group) for group in result.groups), [1, 2, 2])

    def test_shifted_duplicates_still_group_for_four_same_one_unique(self) -> None:
        result = solve_iconcaptcha_data_url(
            self._build_canvas([
                ("circle", -12),
                ("square", 0),
                ("square", 8),
                ("square", 12),
                ("square", -6),
            ])
        )
        self.assertEqual(result.selected_cell_number, 1)
        self.assertEqual(sorted(len(group) for group in result.groups), [1, 4])

    def test_shifted_duplicates_still_group_for_three_vs_two(self) -> None:
        result = solve_iconcaptcha_data_url(
            self._build_canvas([
                ("square", -10),
                ("square", 0),
                ("square", 10),
                ("triangle", 0),
                ("triangle", 10),
            ])
        )
        self.assertEqual(result.selected_cell_number, 4)
        self.assertEqual(sorted(len(group) for group in result.groups), [2, 3])

    def test_eight_cell_strip_can_use_smaller_shift_window(self) -> None:
        result = solve_iconcaptcha_data_url(
            self._build_canvas([
                ("square", -2),
                ("square", 1),
                ("circle", -1),
                ("circle", 2),
                ("triangle", -2),
                ("triangle", 2),
                ("square", 2),
                ("circle", 0),
            ]),
            cell_count=8,
            max_shift=3,
        )
        self.assertEqual(result.selected_cell_number, 5)
        self.assertEqual(sorted(len(group) for group in result.groups), [2, 3, 3])

    def test_white_transparent_icons_can_use_dark_background(self) -> None:
        result = solve_iconcaptcha_data_url(
            self._build_canvas(["square", "circle", "circle", "triangle", "triangle"], fill=(245, 245, 245, 255)),
            background_rgb=(0, 0, 0),
        )
        self.assertEqual(result.selected_cell_number, 1)


if __name__ == "__main__":
    unittest.main()
