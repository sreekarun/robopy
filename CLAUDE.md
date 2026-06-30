# Robo (Python) — project guide

A modern-Python rebuild of the original Node.js robot [sreekarun/robo](https://github.com/sreekarun/robo),
targeting the **Raspberry Pi 5** but fully runnable on **macOS** via stubbed
backends. See `README.md` for the full walkthrough; this file is the quick
orientation for working in the codebase.

## Architecture: everything is a swappable backend

Each subsystem talks to a small abstract interface; a factory picks the backend
per machine (auto-detected, overridable via `ROBO_*` env vars — see `.env.example`).
The control loop, API, and AI brain are identical on Mac and Pi.

| Subsystem | Interface | Mac backend | Pi backend | Stub/CI |
|---|---|---|---|---|
| `hardware/` | `Robot` | — | `gpiozero` (lgpio) | `fake` |
| `speech/` | `Speech` | `mac` (`say`) | `piper` | `fake` |
| `vision/` | `Camera` | `opencv` (webcam) | `picamera2` | `fake` |
| `listen/` | `STT` | `whisper` | `whisper` | `fake` |
| `brain/` | `Brain` | `claude` / `null` | `claude` / `null` | `null` |

`control/loop.py` (`Controller`) owns the hardware, runs the async control loop
(sensors + safety reflex), executes `Command` lists, and keeps conversation
history for the brain. `api/app.py` is FastAPI (REST + WebSocket telemetry +
MJPEG stream). `web/index.html` is the control UI.

## Run / test

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,mac,voice,ai]'   # mac=webcam, voice=whisper, ai=anthropic
ROBO_RELOAD=true robo                   # http://localhost:8000
pytest -q                               # smoke tests, no hardware/API/credits
```

`robo` runs uvicorn without auto-reload unless `ROBO_RELOAD=true`. A
`timeout_graceful_shutdown` is set so the infinite MJPEG stream doesn't hang
reload/Ctrl-C.

## AI brain

`ROBO_BRAIN_ENABLED=true` + a key (`ROBO_ANTHROPIC_API_KEY`, `ANTHROPIC_API_KEY`,
or `ant auth login`) switches `null_brain` (keyword) → `claude_brain`. Model is
`claude-opus-4-8`, `effort=low` for latency. The brain does small talk,
multi-step movement (sequenced with `wait`/`stop`), conversation memory, and
**object identification** via a `look` tool (on-demand camera frame → identify).
Tools map 1:1 to robot `Command`s. Live brain tests cost API credits — keep them
minimal; logic is covered by mocked tests in `tests/test_smoke.py`.

## Secrets

Never commit keys. `.env` is gitignored; use it (or the environment) for
`ROBO_ANTHROPIC_API_KEY`. The repo contains only placeholders and `sk-ant-dummy`
test fixtures.

## Pi notes (Pi 5 specifics)

- GPIO is behind the RP1 chip — legacy `RPi.GPIO`/`pigpio` don't work; use
  `gpiozero` + `lgpio` (`pip install '.[pi]'`).
- No analog input — an **ADS1115** ADC is assumed for the LDR.
- Pin numbers in `hardware/gpiozero_backend.py` are placeholders; match wiring.
- `systemd/robo.service` runs it on boot.
