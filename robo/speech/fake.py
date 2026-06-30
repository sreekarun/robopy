"""No-audio speech backend — just logs. For CI / Linux dev without audio."""
from __future__ import annotations

import logging

from robo.speech.base import Speech

log = logging.getLogger("robo.speech.fake")


class FakeSpeech(Speech):
    async def say(self, text: str) -> None:
        log.info("[say] %s", text)
