"""Speech-to-text interface. Backends: whisper (Mac + Pi), fake.

Two entry points so both capture paths share one engine:
  * transcribe_file  — a browser-recorded audio blob (webm/wav/…); decoded by
    the backend (faster-whisper uses PyAV/ffmpeg).
  * transcribe_array — raw mono float32 PCM from the server-side mic.
"""
from __future__ import annotations

import abc
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class STT(abc.ABC):
    @abc.abstractmethod
    async def transcribe_file(self, path: str) -> str:
        """Transcribe an audio file on disk. Returns text (may be empty)."""

    @abc.abstractmethod
    async def transcribe_array(self, samples: "np.ndarray", sample_rate: int) -> str:
        """Transcribe mono float32 PCM. Returns text (may be empty)."""
