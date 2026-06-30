"""Raspberry Pi 5 backend using gpiozero (lgpio pin factory).

IMPORTANT (Pi 5): the legacy RPi.GPIO and pigpio libraries do NOT work on the
Pi 5 because GPIO moved behind the RP1 chip. gpiozero auto-selects the lgpio
backend on the Pi 5, which is the supported path. Install with: pip install '.[pi]'

Pin numbers below are BCM and are PLACEHOLDERS — set them to match your wiring.
A motor driver such as L298N / DRV8833 / TB6612 sits between these pins and the
motors. For analog sensors (LDR) the Pi has no ADC, so an ADS1115 over I2C is
assumed; wire it up and fill in `_read_light` when ready.
"""
from __future__ import annotations

import logging

from robo.hardware.base import Robot, Telemetry

log = logging.getLogger("robo.hardware.gpiozero")

# --- Wiring (edit these) ---------------------------------------------------
LEFT_MOTOR_PINS = (17, 27)    # (forward, backward) -> motor driver
RIGHT_MOTOR_PINS = (23, 24)
ULTRASONIC_PINS = (5, 6)      # (echo, trigger) -> HC-SR04 (echo needs divider!)
PIR_PIN = 25                  # PIR motion sensor
# ---------------------------------------------------------------------------


class GpioZeroRobot(Robot):
    def __init__(self) -> None:
        # Imported lazily so the module is importable on a Mac (for type checks).
        from gpiozero import DistanceSensor, MotionSensor, Motor

        self._left = Motor(forward=LEFT_MOTOR_PINS[0], backward=LEFT_MOTOR_PINS[1], pwm=True)
        self._right = Motor(forward=RIGHT_MOTOR_PINS[0], backward=RIGHT_MOTOR_PINS[1], pwm=True)
        self._sonar = DistanceSensor(echo=ULTRASONIC_PINS[0], trigger=ULTRASONIC_PINS[1], max_distance=2.0)
        self._pir = MotionSensor(PIR_PIN)
        self._left_speed = 0.0
        self._right_speed = 0.0
        log.info("GpioZeroRobot ready (Pi 5 / lgpio)")

    @staticmethod
    def _apply(motor, speed: float) -> None:
        speed = max(-1.0, min(1.0, speed))
        if speed > 0:
            motor.forward(speed)
        elif speed < 0:
            motor.backward(-speed)
        else:
            motor.stop()

    def drive(self, left: float, right: float) -> None:
        self._left_speed = max(-1.0, min(1.0, left))
        self._right_speed = max(-1.0, min(1.0, right))
        self._apply(self._left, self._left_speed)
        self._apply(self._right, self._right_speed)

    def _read_light(self) -> float | None:
        # TODO: read ADS1115 channel here (Adafruit Blinka / smbus2). None for now.
        return None

    def read(self) -> Telemetry:
        return Telemetry(
            left_speed=self._left_speed,
            right_speed=self._right_speed,
            distance_cm=round(self._sonar.distance * 100.0, 1),
            motion_detected=bool(self._pir.motion_detected),
            light_level=self._read_light(),
        )

    def close(self) -> None:
        self.stop()
        for dev in (self._left, self._right, self._sonar, self._pir):
            try:
                dev.close()
            except Exception:  # noqa: BLE001 - best-effort cleanup
                pass
