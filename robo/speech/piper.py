"""Neural TTS on the Raspberry Pi via Piper.

Setup on the Pi:
    pip install piper-tts        # or use the prebuilt binary release
    # download a voice, e.g. en_US-amy-medium.onnx (+ .json) from the Piper repo

Then play through ALSA with `aplay`. Adjust paths to your voice model.
"""
from __future__ import annotations

import asyncio
import logging

from robo.speech.base import Speech

log = logging.getLogger("robo.speech.piper")


class PiperSpeech(Speech):
    def __init__(self, model_path: str = "voices/en_US-amy-medium.onnx") -> None:
        self._model = model_path
        log.info("PiperSpeech ready (model=%s)", model_path)

    async def say(self, text: str) -> None:
        # piper synthesizes WAV to stdout; aplay plays it.
        piper = await asyncio.create_subprocess_exec(
            "piper", "--model", self._model, "--output_file", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        wav, _ = await piper.communicate(text.encode())
        aplay = await asyncio.create_subprocess_exec(
            "aplay", "-q", "-", stdin=asyncio.subprocess.PIPE
        )
        await aplay.communicate(wav)
