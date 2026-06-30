from __future__ import annotations

import logging

from robo.config import settings
from robo.listen.base import STT

log = logging.getLogger("robo.listen")


def make_stt() -> STT:
    backend = settings.resolved_stt()
    log.info("stt backend: %s", backend)

    if backend == "whisper":
        from robo.listen.whisper_stt import WhisperSTT
        return WhisperSTT()
    if backend == "fake":
        from robo.listen.fake import FakeSTT
        return FakeSTT()

    raise ValueError(f"Unknown stt backend: {backend!r}")
