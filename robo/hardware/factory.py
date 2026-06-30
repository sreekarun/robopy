from __future__ import annotations

import logging

from robo.config import settings
from robo.hardware.base import Robot

log = logging.getLogger("robo.hardware")


def make_robot() -> Robot:
    backend = settings.resolved_hardware()
    log.info("hardware backend: %s", backend)

    if backend == "fake":
        from robo.hardware.fake import FakeRobot
        return FakeRobot()
    if backend == "gpiozero":
        from robo.hardware.gpiozero_backend import GpioZeroRobot
        return GpioZeroRobot()

    raise ValueError(f"Unknown hardware backend: {backend!r}")
