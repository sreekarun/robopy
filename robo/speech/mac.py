"""macOS text-to-speech via the built-in `say` command. No install needed.

List voices with: `say -v '?'`  (e.g. "Samantha", "Daniel", "Karen").
"""
from __future__ import annotations

import asyncio
import logging

from robo.speech.base import Speech

log = logging.getLogger("robo.speech.mac")


class MacSaySpeech(Speech):
    def __init__(self, voice: str | None = None, rate_wpm: int | None = None) -> None:
        self._voice = voice
        self._rate = rate_wpm
        log.info("MacSaySpeech ready (voice=%s)", voice or "default")

    async def say(self, text: str) -> None:
        cmd = ["say"]
        if self._voice:
            cmd += ["-v", self._voice]
        if self._rate:
            cmd += ["-r", str(self._rate)]
        cmd.append(text)
        log.debug("say: %s", text)
        proc = await asyncio.create_subprocess_exec(*cmd)
        await proc.wait()
