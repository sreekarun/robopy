from __future__ import annotations

import logging

from robo.brain.base import Brain
from robo.config import settings

log = logging.getLogger("robo.brain")


def make_brain() -> Brain:
    if settings.brain_enabled:
        from robo.brain.claude_brain import ClaudeBrain
        log.info("brain: claude")
        return ClaudeBrain()
    from robo.brain.null_brain import NullBrain
    log.info("brain: null (keyword). Set ROBO_BRAIN_ENABLED=true to use Claude.")
    return NullBrain()
