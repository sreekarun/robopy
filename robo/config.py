"""Central configuration.

Backends are auto-detected by platform but can be forced with env vars, e.g.:

    ROBO_HARDWARE=fake ROBO_SPEECH=mac robo
"""
from __future__ import annotations

import platform

from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_raspberry_pi() -> bool:
    """True when running on a Raspberry Pi (checks the device-tree model)."""
    try:
        with open("/proc/device-tree/model", "rb") as fh:
            return b"Raspberry Pi" in fh.read()
    except OSError:
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ROBO_", env_file=".env")

    # "auto" resolves to "gpiozero" on a Pi, else "fake".
    hardware: str = "auto"
    # "auto" resolves to "mac" on macOS, "piper" on a Pi, else "fake".
    speech: str = "auto"

    # Web server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False  # auto-restart on code changes (dev only)

    # Camera. "auto" -> opencv on macOS (default webcam), picamera2 on a Pi,
    # else fake (synthetic frames).
    camera: str = "auto"
    camera_index: int = 0          # webcam device index for the opencv backend
    camera_width: int = 640
    camera_height: int = 480
    camera_fps: int = 15           # MJPEG stream target frame rate

    # Voice / speech-to-text (enable with the `voice` extra).
    #   stt: "auto" -> whisper if faster-whisper is installed, else fake.
    stt: str = "auto"
    whisper_model: str = "tiny.en"   # tiny.en/base.en are good on a Pi 5
    whisper_compute: str = "int8"    # int8 is fast on CPU (Pi); "auto" on Mac
    mic_sample_rate: int = 16000     # whisper wants 16 kHz mono
    mic_device: int | None = None    # sounddevice index; None = system default
    # Energy-VAD: start an utterance above `vad_start`, end after `vad_silence_s`.
    vad_start: float = 0.02
    vad_silence_s: float = 0.8
    vad_max_s: float = 8.0
    # Optional wake word — if set, only utterances containing it are acted on.
    wake_word: str = ""

    # AI brain (off by default — enable when you add the `ai` extra)
    brain_enabled: bool = False
    anthropic_api_key: str | None = None
    brain_model: str = "claude-opus-4-8"
    brain_effort: str = "low"  # low|medium|high|max — low keeps reflexes snappy
    # When true, /api/instruct attaches a camera frame so the brain can "see".
    vision_default: bool = False

    def resolved_hardware(self) -> str:
        if self.hardware != "auto":
            return self.hardware
        return "gpiozero" if _is_raspberry_pi() else "fake"

    def resolved_speech(self) -> str:
        if self.speech != "auto":
            return self.speech
        if platform.system() == "Darwin":
            return "mac"
        return "piper" if _is_raspberry_pi() else "fake"

    def resolved_camera(self) -> str:
        if self.camera != "auto":
            return self.camera
        if platform.system() == "Darwin":
            return "opencv"
        return "picamera2" if _is_raspberry_pi() else "fake"

    def resolved_stt(self) -> str:
        if self.stt != "auto":
            return self.stt
        try:
            import faster_whisper  # noqa: F401
            return "whisper"
        except ImportError:
            return "fake"


settings = Settings()
