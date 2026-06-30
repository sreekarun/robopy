"""Synthetic camera — renders a moving scene with Pillow. No hardware/CI-safe.

Draws a bouncing ball and a live timestamp so the MJPEG stream visibly updates
and the AI vision path has a real (if silly) image to reason about.
"""
from __future__ import annotations

import io
import logging
import math
import time

from robo.config import settings
from robo.vision.base import Camera

log = logging.getLogger("robo.vision.fake")


class FakeCamera(Camera):
    def __init__(self) -> None:
        self._w = settings.camera_width
        self._h = settings.camera_height
        self._t0 = time.monotonic()
        log.info("FakeCamera ready (synthetic %dx%d)", self._w, self._h)

    def _render(self) -> bytes:
        from PIL import Image, ImageDraw

        t = time.monotonic() - self._t0
        img = Image.new("RGB", (self._w, self._h), (18, 18, 24))
        draw = ImageDraw.Draw(img)

        # bouncing ball
        x = (math.sin(t) * 0.5 + 0.5) * (self._w - 60) + 30
        y = (math.sin(t * 1.7) * 0.5 + 0.5) * (self._h - 60) + 30
        draw.ellipse([x - 24, y - 24, x + 24, y + 24], fill=(43, 108, 255))

        draw.rectangle([0, 0, self._w - 1, self._h - 1], outline=(60, 60, 70), width=2)
        draw.text((12, 10), "robo · fake camera", fill=(200, 200, 210))
        draw.text((12, self._h - 22), time.strftime("%H:%M:%S"), fill=(150, 150, 160))

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()

    async def read_jpeg(self) -> bytes | None:
        return self._render()
