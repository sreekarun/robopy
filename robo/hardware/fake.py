"""Simulated robot — runs anywhere (your Mac, CI). No hardware required.

Keeps a tiny internal world model so the control loop and UI do something
believable: it "moves," and a virtual wall drifts closer/farther so obstacle
avoidance can be exercised without a real ultrasonic sensor.
"""
from __future__ import annotations

import logging
import math
import random
import time

from robo.hardware.base import Robot, Telemetry

log = logging.getLogger("robo.hardware.fake")


class FakeRobot(Robot):
    def __init__(self) -> None:
        self._left = 0.0
        self._right = 0.0
        self._wall_cm = 120.0
        self._t0 = time.monotonic()
        log.info("FakeRobot ready (no hardware)")

    def drive(self, left: float, right: float) -> None:
        self._left = max(-1.0, min(1.0, left))
        self._right = max(-1.0, min(1.0, right))
        log.debug("drive L=%.2f R=%.2f", self._left, self._right)

    def read(self) -> Telemetry:
        # Forward motion eats into the distance to the virtual wall.
        forward = (self._left + self._right) / 2.0
        self._wall_cm -= forward * 5.0
        if self._wall_cm < 8.0:
            self._wall_cm = random.uniform(80.0, 150.0)  # "drove past it"
        self._wall_cm = min(self._wall_cm, 200.0)

        elapsed = time.monotonic() - self._t0
        return Telemetry(
            left_speed=self._left,
            right_speed=self._right,
            distance_cm=round(self._wall_cm, 1),
            motion_detected=random.random() < 0.02,
            light_level=round(0.5 + 0.4 * math.sin(elapsed / 5.0), 3),
        )
