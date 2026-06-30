"""Entry point: `robo` (after pip install) or `python -m robo.main`."""
from __future__ import annotations

import logging

import uvicorn

from robo.config import settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    log = logging.getLogger("robo")
    log.info(
        "starting robo  hardware=%s speech=%s brain=%s  http://%s:%d",
        settings.resolved_hardware(),
        settings.resolved_speech(),
        "claude" if settings.brain_enabled else "null",
        settings.host,
        settings.port,
    )
    uvicorn.run(
        "robo.api.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        reload_dirs=["robo", "web"] if settings.reload else None,
        # The MJPEG stream is an infinite response; without a bound, graceful
        # shutdown (and therefore --reload) would hang waiting for it to close.
        timeout_graceful_shutdown=3,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
