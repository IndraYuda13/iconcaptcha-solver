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
