from __future__ import annotations

import logging

from robo.config import settings
from robo.speech.base import Speech

log = logging.getLogger("robo.speech")


def make_speech() -> Speech:
    backend = settings.resolved_speech()
    log.info("speech backend: %s", backend)

    if backend == "mac":
        from robo.speech.mac import MacSaySpeech
        return MacSaySpeech()
    if backend == "piper":
        from robo.speech.piper import PiperSpeech
        return PiperSpeech()
    if backend == "fake":
        from robo.speech.fake import FakeSpeech
        return FakeSpeech()

    raise ValueError(f"Unknown speech backend: {backend!r}")
