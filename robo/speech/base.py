"""Text-to-speech interface. Backends: mac (`say`), piper (Pi), fake (logs)."""
from __future__ import annotations

import abc


class Speech(abc.ABC):
    @abc.abstractmethod
    async def say(self, text: str) -> None:
        """Speak `text`. Returns when playback finishes."""

    async def close(self) -> None:
        """Release any resources."""
