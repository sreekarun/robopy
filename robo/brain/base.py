"""The AI 'brain' seam.

A Brain turns a natural-language instruction (plus current telemetry, and later
a camera frame) into a list of robot Commands. Today there's a keyword-matching
NullBrain so the plumbing works end-to-end with no API key. Tomorrow, drop in
ClaudeBrain (tool-use) and the robot understands free-form speech — no changes
needed anywhere else.
"""
from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from robo.hardware.base import Telemetry

Action = Literal["drive", "stop", "say", "wait"]


@dataclass
class Command:
    action: Action
    # drive:
    left: float = 0.0
    right: float = 0.0
    # say:
    text: str = ""
    # wait:
    seconds: float = 0.0


@dataclass
class Perception:
    """Everything the brain gets to 'see' for one decision."""
    instruction: str
    telemetry: Telemetry
    image_jpeg: bytes | None = None  # camera frame pre-attached (explicit vision)
    # Recent conversation as plain-text API turns: [{"role","content"}, ...].
    history: list[dict] = field(default_factory=list)
    # Lets the brain grab a fresh camera frame on demand (the `look` tool).
    grab_frame: Callable[[], Awaitable[bytes | None]] | None = None


class Brain(abc.ABC):
    @abc.abstractmethod
    async def decide(self, perception: Perception) -> list[Command]:
        """Return the commands to execute for this instruction."""
