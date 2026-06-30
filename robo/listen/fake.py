"""Fake STT — returns canned text so the voice pipeline runs without whisper.

Set ROBO_STT=fake (or just don't install the voice extra). Useful for CI and
for exercising the API/UI plumbing without downloading a model.
"""
from __future__ import annotations

import logging

from robo.listen.base import STT

log = logging.getLogger("robo.listen.fake")


class FakeSTT(STT):
    def __init__(self, canned: str = "go forward") -> None:
        self._canned = canned
        log.info("FakeSTT ready (always returns %r)", canned)

    async def transcribe_file(self, path: str) -> str:
        return self._canned

    async def transcribe_array(self, samples, sample_rate: int) -> str:
        return self._canned
