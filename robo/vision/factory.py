from __future__ import annotations

import logging

from robo.config import settings
from robo.vision.base import Camera

log = logging.getLogger("robo.vision")


def make_camera() -> Camera:
    backend = settings.resolved_camera()
    log.info("camera backend: %s", backend)

    if backend == "opencv":
        from robo.vision.opencv_backend import OpenCVCamera
        return OpenCVCamera()
    if backend == "picamera2":
        from robo.vision.picamera2_backend import Picamera2Camera
        return Picamera2Camera()
    if backend == "fake":
        from robo.vision.fake import FakeCamera
        return FakeCamera()

    raise ValueError(f"Unknown camera backend: {backend!r}")
