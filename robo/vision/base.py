"""Camera interface. Backends: opencv (Mac webcam), picamera2 (Pi), fake.

Everything downstream — the MJPEG stream, the snapshot endpoint, and the AI
vision path — only deals in JPEG bytes, so swapping cameras changes nothing
above this layer.
"""
from __future__ import annotations

import abc
import asyncio
from collections.abc import AsyncIterator


class Camera(abc.ABC):
    @abc.abstractmethod
    async def read_jpeg(self) -> bytes | None:
        """Grab the latest frame as JPEG bytes, or None if unavailable."""

    async def frames(self, fps: int) -> AsyncIterator[bytes]:
        """Yield JPEG frames at roughly `fps` — used by the MJPEG stream."""
        period = 1.0 / max(1, fps)
        while True:
            frame = await self.read_jpeg()
            if frame is not None:
                yield frame
            await asyncio.sleep(period)

    def close(self) -> None:
        """Release the device. Safe to call multiple times."""
