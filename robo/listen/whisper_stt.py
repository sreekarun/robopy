"""faster-whisper speech-to-text. Runs on Mac and Raspberry Pi 5.

Install with: pip install '.[voice]'

The model downloads once on first use (tiny.en ~75 MB) and is cached under
~/.cache/huggingface. On a Pi 5, tiny.en/base.en with int8 compute are a good
balance of speed and accuracy; on a Mac you can bump whisper_model to small.en.

Transcription is CPU-bound, so it runs in a thread executor to keep asyncio free.
"""
from __future__ import annotations

import asyncio
import logging

from robo.config import settings
from robo.listen.base import STT

log = logging.getLogger("robo.listen.whisper")


class WhisperSTT(STT):
    def __init__(self) -> None:
        from faster_whisper import WhisperModel  # lazy

        compute = settings.whisper_compute
        self._model = WhisperModel(settings.whisper_model, device="cpu", compute_type=compute)
        log.info("WhisperSTT ready (model=%s compute=%s)", settings.whisper_model, compute)

    def _run(self, audio, **kw) -> str:
        # audio: a file path (str) or a float32 numpy array at 16 kHz mono.
        segments, _info = self._model.transcribe(audio, beam_size=1, **kw)
        return " ".join(seg.text for seg in segments).strip()

    async def transcribe_file(self, path: str) -> str:
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, lambda: self._run(path))
        log.debug("file transcript: %s", text)
        return text

    async def transcribe_array(self, samples, sample_rate: int) -> str:
        # faster-whisper expects 16 kHz mono float32; resample if needed.
        if sample_rate != 16000:
            samples = _resample(samples, sample_rate, 16000)
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, lambda: self._run(samples))
        log.debug("array transcript: %s", text)
        return text


def _resample(samples, src_rate: int, dst_rate: int):
    import numpy as np

    if src_rate == dst_rate:
        return samples
    n_dst = int(round(len(samples) * dst_rate / src_rate))
    x_src = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
    x_dst = np.linspace(0.0, 1.0, num=n_dst, endpoint=False)
    return np.interp(x_dst, x_src, samples).astype("float32")
