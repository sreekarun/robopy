"""Server-side microphone capture with a simple energy gate (VAD).

This is the robot's own ear — used on the Pi 5 (USB mic / I2S hat) and on any
Mac with a mic. It records discrete utterances: it waits for the input level to
rise above `vad_start`, captures until it stays quiet for `vad_silence_s`, and
returns the utterance as mono float32 at the capture rate.

Needs the `voice` extra (sounddevice). On the Pi also: sudo apt install libportaudio2
"""
from __future__ import annotations

import asyncio
import logging

from robo.config import settings

log = logging.getLogger("robo.listen.mic")


class Microphone:
    def __init__(self) -> None:
        import numpy as np  # noqa: F401  (validate deps early)
        import sounddevice  # noqa: F401

        self._rate = settings.mic_sample_rate
        self._device = settings.mic_device
        log.info("Microphone ready (rate=%d device=%s)", self._rate, self._device)

    def _record_utterance(self):
        """Blocking: capture one utterance. Returns float32 ndarray or None."""
        import numpy as np
        import sounddevice as sd

        block = int(self._rate * 0.03)  # 30 ms blocks
        silence_blocks = int(settings.vad_silence_s / 0.03)
        max_blocks = int(settings.vad_max_s / 0.03)

        captured: list = []
        triggered = False
        quiet_run = 0

        with sd.InputStream(
            samplerate=self._rate, channels=1, dtype="float32",
            blocksize=block, device=self._device,
        ) as stream:
            for _ in range(max_blocks + silence_blocks):
                data, _overflow = stream.read(block)
                mono = data[:, 0]
                level = float(np.sqrt(np.mean(mono ** 2)))  # RMS
                if not triggered:
                    if level >= settings.vad_start:
                        triggered = True
                        captured.append(mono.copy())
                else:
                    captured.append(mono.copy())
                    quiet_run = quiet_run + 1 if level < settings.vad_start else 0
                    if quiet_run >= silence_blocks:
                        break
                if triggered and len(captured) >= max_blocks:
                    break

        if not captured:
            return None
        return np.concatenate(captured)

    async def listen_utterance(self):
        """Async wrapper — returns a captured utterance (float32 ndarray)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._record_utterance)

    @property
    def sample_rate(self) -> int:
        return self._rate
