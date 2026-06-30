"""Raspberry Pi camera via picamera2 (the modern libcamera stack on Pi OS).

Works with the Pi Camera Module on the Pi 5. Install with: pip install '.[pi]'
(picamera2 is usually preinstalled on Raspberry Pi OS; if so, create the venv
with `--system-site-packages` so it's visible.)
"""
from __future__ import annotations

import asyncio
import io
import logging

from robo.config import settings
from robo.vision.base import Camera

log = logging.getLogger("robo.vision.picamera2")


class Picamera2Camera(Camera):
    def __init__(self) -> None:
        from picamera2 import Picamera2  # lazy

        self._picam = Picamera2()
        config = self._picam.create_video_configuration(
            main={"size": (settings.camera_width, settings.camera_height), "format": "RGB888"}
        )
        self._picam.configure(config)
        self._picam.start()
        self._lock = asyncio.Lock()
        log.info("Picamera2Camera ready (%dx%d)", settings.camera_width, settings.camera_height)

    def _grab(self) -> bytes | None:
        from PIL import Image

        array = self._picam.capture_array()
        buf = io.BytesIO()
        Image.fromarray(array).save(buf, format="JPEG", quality=80)
        return buf.getvalue()

    async def read_jpeg(self) -> bytes | None:
        async with self._lock:
            return await asyncio.get_running_loop().run_in_executor(None, self._grab)

    def close(self) -> None:
        try:
            self._picam.stop()
            self._picam.close()
        except Exception:  # noqa: BLE001
            pass
