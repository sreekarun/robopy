# Robo (Python)

A rebuild of [robo](https://github.com/sreekarun/robo) in modern Python for the
**Raspberry Pi 5** — but it runs on your **Mac** too, using stubbed hardware and
the built-in `say` voice, so you can build the whole thing before any wiring.

## Architecture

Everything talks to small abstract interfaces, and a factory picks the right
backend per machine. Same control loop, API, and AI brain everywhere.

```
robo/
  config.py            # settings + platform auto-detection
  hardware/            # Robot interface
    fake.py            #   -> Mac/CI (simulated world)
    gpiozero_backend.py#   -> Pi 5 (gpiozero + lgpio)
  speech/              # Speech interface
    mac.py             #   -> macOS `say`
    piper.py           #   -> Pi neural TTS
    fake.py            #   -> logs only
  vision/              # Camera interface
    opencv_backend.py  #   -> Mac/any webcam (OpenCV)
    picamera2_backend.py #  -> Pi Camera Module
    fake.py            #   -> synthetic moving scene
  listen/              # Speech-to-text (voice commands)
    whisper_stt.py     #   -> faster-whisper (Mac + Pi, offline)
    mic.py             #   -> server-side mic capture + energy VAD (the Pi robot)
    voice_loop.py      #   -> continuous listen -> instruct, optional wake word
    fake.py            #   -> canned text
  brain/               # AI seam: NL instruction (+ camera frame) -> commands
    null_brain.py      #   -> keyword matcher (no API key)
    claude_brain.py    #   -> Claude tool-use (the supercharge path)
  control/loop.py      # async heartbeat: sensors, safety, command exec
  api/app.py           # FastAPI REST + WebSocket telemetry
web/index.html         # control UI
systemd/robo.service   # boot/restart on the Pi
```

Backend selection is automatic (`auto`) but overridable:
`ROBO_HARDWARE`, `ROBO_SPEECH` (see `.env.example`).

## Run on your Mac

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,mac]'   # 'mac' adds opencv for the webcam
robo                          # -> http://localhost:8000
```

Open the UI: see the **live camera feed**, drive with the arrows (simulated
motors), type a phrase and hit **Speak** to hear your Mac talk, or send a
natural-language instruction.

**Webcam:** with the `mac` extra installed, the default webcam (device index 0)
is used automatically. The first run triggers a macOS camera-permission prompt
for your terminal app — approve it and restart `robo`. No webcam / headless?
Set `ROBO_CAMERA=fake` for a synthetic feed.

Camera endpoints: `GET /snapshot.jpg` (single frame), `GET /stream.mjpg` (MJPEG).

```bash
pytest                     # smoke tests, no hardware
```

## Deploy to the Raspberry Pi 5

```bash
git clone <your-repo> ~/robopy && cd ~/robopy
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[pi]'     # gpiozero + lgpio + picamera2
# edit pin numbers in robo/hardware/gpiozero_backend.py to match your wiring
sudo cp systemd/robo.service /etc/systemd/system/
sudo systemctl enable --now robo
```

> **Pi 5 note:** GPIO sits behind the new RP1 chip — legacy `RPi.GPIO`/`pigpio`
> don't work. This project uses `gpiozero` with the `lgpio` backend, which does.
> The Pi has no analog input, so an **ADS1115** ADC is assumed for the LDR.

## Supercharge with AI

The `brain/` seam already exists. To switch from keyword matching to Claude:

```bash
pip install -e '.[ai]'
export ROBO_BRAIN_ENABLED=true ROBO_ANTHROPIC_API_KEY=sk-ant-...
robo
```

Credentials resolve from `ROBO_ANTHROPIC_API_KEY`, a plain `ANTHROPIC_API_KEY`,
or an `ant auth login` profile. Model is `claude-opus-4-8`; `ROBO_BRAIN_EFFORT`
(default `low`) trades reasoning depth for control-loop latency.

Now `/api/instruct` (and the UI's command box) sends the instruction + live
telemetry to Claude, which calls robot tools (`drive`/`stop`/`say`/`wait`).
Robo is conversational with the brain on:

- **Small talk** — greetings, questions, jokes ("what's your name?", "how are
  you?") get a short spoken reply and *no* movement.
- **Multi-step orders** — *"go forward then turn left"* is sequenced with
  `wait`s and a closing `stop`.
- **Conversation memory** — the controller keeps a short rolling history, so
  follow-ups have context ("what did I just ask you?", "do that again").

The keyword `NullBrain` only knows simple one-word commands and a couple of
canned greetings — real conversation needs `ClaudeBrain`.

**Vision is already wired:** tick *"Let the robot see"* in the UI (or send
`{"use_vision": true}` to `/api/instruct`, or set `ROBO_VISION_DEFAULT=true`)
and a live camera frame is attached to the request — `ClaudeBrain` forwards it
as an image block, so Claude reasons over what the camera sees. Same on Mac
(webcam) and Pi (camera module).

## Voice commands

Speech-to-text via **faster-whisper** (offline, runs on both Mac and Pi 5).

```bash
pip install -e '.[voice]'   # faster-whisper + sounddevice
robo
```

Two ways to talk to the robot, both feeding the same `instruct` pipeline:

- **Hold to talk (browser):** the 🎤 button records in the browser and POSTs the
  clip to `/api/voice`; the server transcribes and acts. Great for Mac dev — uses
  the browser mic, no server audio setup. (Grant the browser mic permission.)
- **Robot's own ears (server mic):** toggle *"Robot ears"* (or `POST /api/listening
  {on:true}`) to run a continuous mic loop with energy-VAD — this is the headless
  mode for the Pi. On the Pi: `sudo apt install libportaudio2` for sounddevice.

Tuning (see `.env.example`): `ROBO_WHISPER_MODEL` (tiny.en/base.en/small.en),
`ROBO_WAKE_WORD` (e.g. `robo` — only act on "robo, …"), and the `ROBO_VAD_*`
thresholds. First run downloads the model (~75 MB for tiny.en).

> Verified end-to-end on Mac: `say "robo, go forward and then turn left"` →
> whisper → `"Robo, go forward and then turn left."` → brain → drive commands.
