"""Continuous voice loop: mic utterance -> STT -> (wake word) -> handler.

Toggle it on/off (e.g. from the API). On the robot you'd leave it on with a
wake word set, so it only acts when it hears "robo, go forward".
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from robo.config import settings
from robo.listen.base import STT

log = logging.getLogger("robo.listen.loop")

Handler = Callable[[str], Awaitable[object]]


class VoiceLoop:
    def __init__(self, stt: STT, handler: Handler) -> None:
        self._stt = stt
        self._handler = handler
        self._task: asyncio.Task | None = None
        self._mic = None
        self.last_transcript: str = ""

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        from robo.listen.mic import Microphone  # lazy: needs sounddevice

        self._mic = Microphone()
        self._task = asyncio.create_task(self._run())
        log.info("voice loop started (wake_word=%r)", settings.wake_word or "(none)")

    def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        log.info("voice loop stopped")

    def _matches_wake_word(self, text: str) -> str | None:
        """Return the actionable command, or None if the wake word is missing."""
        wake = settings.wake_word.lower().strip()
        if not wake:
            return text
        low = text.lower()
        if wake not in low:
            return None
        # strip everything up to and including the wake word
        return text[low.index(wake) + len(wake):].strip(" ,.!") or text

    async def _run(self) -> None:
        try:
            while True:
                audio = await self._mic.listen_utterance()
                if audio is None or len(audio) == 0:
                    continue
                text = await self._stt.transcribe_array(audio, self._mic.sample_rate)
                if not text:
                    continue
                self.last_transcript = text
                command = self._matches_wake_word(text)
                if command is None:
                    log.debug("ignored (no wake word): %s", text)
                    continue
                log.info("heard: %s", command)
                await self._handler(command)
        except asyncio.CancelledError:
            pass
