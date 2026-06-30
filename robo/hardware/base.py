"""Abstract hardware interface.

Every backend (fake on Mac, gpiozero on the Pi) implements `Robot`. The rest of
the codebase only ever talks to this interface, so the same control loop, API,
and AI brain run unchanged on your laptop and on the robot.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class Telemetry:
    """A snapshot of the robot's state, published to the UI / AI brain."""
    left_speed: float = 0.0       # -1.0 .. 1.0
    right_speed: float = 0.0      # -1.0 .. 1.0
    distance_cm: float | None = None   # forward ultrasonic, None if unread
    motion_detected: bool = False      # PIR
    light_level: float | None = None   # 0.0 .. 1.0 from LDR via ADC


class Robot(abc.ABC):
    """The physical (or simulated) robot."""

    @abc.abstractmethod
    def drive(self, left: float, right: float) -> None:
        """Set track/wheel speeds, each in [-1.0, 1.0]. Differential drive."""

    def stop(self) -> None:
        self.drive(0.0, 0.0)

    # Convenience movement helpers built on `drive`.
    def forward(self, speed: float = 1.0) -> None:
        self.drive(speed, speed)

    def backward(self, speed: float = 1.0) -> None:
        self.drive(-speed, -speed)

    def turn_left(self, speed: float = 1.0) -> None:
        self.drive(-speed, speed)

    def turn_right(self, speed: float = 1.0) -> None:
        self.drive(speed, -speed)

    @abc.abstractmethod
    def read(self) -> Telemetry:
        """Read all sensors and return a fresh snapshot."""

    def close(self) -> None:
        """Release hardware resources. Safe to call multiple times."""
        self.stop()
