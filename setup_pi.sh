#!/usr/bin/env bash
# setup_pi.sh — one-shot setup for Robo on a Raspberry Pi 5
#
# Usage (run from the repo root as a regular user with sudo access):
#   bash setup_pi.sh [--voice] [--ai]
#
#   --voice   Install faster-whisper + sounddevice for speech-to-text
#   --ai      Install the anthropic SDK and prompt for ROBO_ANTHROPIC_API_KEY
#
# The Piper TTS voice model is always downloaded as part of the base install
# because the default Pi speech backend (`piper`) requires it.
#
# Example (full install with voice and AI):
#   bash setup_pi.sh --voice --ai

set -euo pipefail

# ── Flags ────────────────────────────────────────────────────────────────────
INSTALL_VOICE=false
INSTALL_AI=false
for arg in "$@"; do
  case "$arg" in
    --voice) INSTALL_VOICE=true ;;
    --ai)    INSTALL_AI=true ;;
    --voice=*|--ai=*)
      echo "Unknown flag: $arg  (use --voice or --ai without a value)"; exit 1 ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"

# ── Helpers ──────────────────────────────────────────────────────────────────
step() { echo; echo "── $* ──────────────────────────────────────────────────"; }
ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠  $*"; }

# ── Platform check ────────────────────────────────────────────────────────────
step "Checking platform"
if grep -qi "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
  PI_MODEL=$(tr -d '\0' < /proc/device-tree/model)
  ok "Running on: $PI_MODEL"
else
  warn "This machine does not appear to be a Raspberry Pi."
  warn "The gpiozero / lgpio / picamera2 packages may fail to install or run."
  read -rp "  Continue anyway? [y/N] " _ans
  [[ "$_ans" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
fi

# ── System packages ───────────────────────────────────────────────────────────
step "Installing system packages (apt)"
APT_PKGS=(
  python3-venv      # venv support
  python3-dev       # headers for compiling any C extensions
  python3-pip       # bootstrap pip inside the venv
  git               # in case the repo was downloaded as a zip
  curl              # downloading the Piper TTS voice model
  alsa-utils        # aplay — plays Piper TTS output
  libjpeg-dev       # Pillow / camera image encoding
)
if $INSTALL_VOICE; then
  APT_PKGS+=(libportaudio2)   # sounddevice needs PortAudio for the server mic
fi

sudo apt-get update -qq
# shellcheck disable=SC2068  # intentional word-splitting of array
sudo apt-get install -y -qq ${APT_PKGS[@]}
ok "System packages installed"

# ── Python virtual environment ────────────────────────────────────────────────
step "Setting up Python virtual environment"
if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
  ok "Created $VENV_DIR"
else
  ok "Re-using existing $VENV_DIR"
fi
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
ok "Activated venv and upgraded pip"

# ── Robo + Pi extras ──────────────────────────────────────────────────────────
step "Installing Robo with Pi extras (gpiozero + lgpio + picamera2 + piper-tts)"
cd "$REPO_DIR"
pip install -e '.[pi]' --quiet
ok "Installed .[pi]"

# ── Piper TTS voice model ─────────────────────────────────────────────────────
# Always downloaded: the default Pi speech backend is `piper`, which needs the
# model file at startup. Without it, TTS will fail even on a base install.
VOICES_DIR="$REPO_DIR/voices"
VOICE_ONNX="$VOICES_DIR/en_US-amy-medium.onnx"
VOICE_JSON="$VOICES_DIR/en_US-amy-medium.onnx.json"
if [[ -f "$VOICE_ONNX" && -f "$VOICE_JSON" ]]; then
  step "Piper TTS voice model"
  ok "Voice model already present — skipping download"
else
  step "Downloading Piper TTS voice model (en_US-amy-medium)"
  mkdir -p "$VOICES_DIR"
  BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"
  curl -fL --progress-bar -o "$VOICE_ONNX" "$BASE_URL/en_US-amy-medium.onnx"
  curl -fL --progress-bar -o "$VOICE_JSON" "$BASE_URL/en_US-amy-medium.onnx.json"
  ok "Voice model saved to $VOICES_DIR/"
fi

# ── Voice / STT extras ────────────────────────────────────────────────────────
if $INSTALL_VOICE; then
  step "Installing voice / STT extras (faster-whisper + sounddevice)"
  pip install -e '.[voice]' --quiet
  ok "Installed .[voice]"
fi

# ── AI brain extras ───────────────────────────────────────────────────────────
if $INSTALL_AI; then
  step "Installing AI brain extras (anthropic SDK)"
  pip install -e '.[ai]' --quiet
  ok "Installed .[ai]"
fi

# ── .env configuration ────────────────────────────────────────────────────────
step "Configuring .env"
ENV_FILE="$REPO_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$REPO_DIR/.env.example" "$ENV_FILE"
  ok "Created .env from .env.example"
else
  ok ".env already exists — leaving it unchanged"
fi

# Set or update a KEY=VALUE in the .env file idempotently.
_set_env() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
  else
    echo "${key}=${val}" >> "$ENV_FILE"
  fi
}

if $INSTALL_AI; then
  read -rsp "  Enter your Anthropic API key (blank to skip): " _ant_key
  echo  # newline after silent input
  if [[ -n "$_ant_key" ]]; then
    _set_env "ROBO_BRAIN_ENABLED" "true"
    _set_env "ROBO_ANTHROPIC_API_KEY" "$_ant_key"
    ok "API key and ROBO_BRAIN_ENABLED=true written to .env"
  else
    warn "No key entered — set ROBO_BRAIN_ENABLED=true and ROBO_ANTHROPIC_API_KEY in .env later"
  fi
fi

# ── systemd service ───────────────────────────────────────────────────────────
step "Installing systemd service"
SERVICE_SRC="$REPO_DIR/systemd/robo.service"
SERVICE_DST="/etc/systemd/system/robo.service"

# Patch the service file to reflect the actual install location and user,
# rather than the hard-coded defaults (User=pi, /home/pi/robopy).
sed \
  -e "s|User=pi|User=${USER}|g" \
  -e "s|/home/pi/robopy|${REPO_DIR}|g" \
  "$SERVICE_SRC" | sudo tee "$SERVICE_DST" > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable robo
ok "robo.service installed for user=${USER}, WorkingDirectory=${REPO_DIR}"

read -rp "  Start the service now? [Y/n] " _start_now
if [[ ! "$_start_now" =~ ^[Nn]$ ]]; then
  sudo systemctl restart robo
  sleep 2
  if systemctl is-active --quiet robo; then
    ok "robo.service is running"
  else
    warn "robo.service did not start cleanly — check logs:"
    warn "  journalctl -u robo -f"
  fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════════════════"
echo "  Setup complete!"
echo
echo "  Web UI: http://$(hostname -I | awk '{print $1}' 2>/dev/null || echo '<pi-ip>'):8000"
echo
echo "  Useful commands:"
echo "    journalctl -u robo -f           # live service logs"
echo "    sudo systemctl restart robo     # restart after a code change"
echo "    sudo systemctl stop robo        # stop the service"
echo "    source .venv/bin/activate       # activate the Python venv"
echo
if ! $INSTALL_VOICE; then
  echo "  Tip: re-run with --voice to add speech-to-text support"
fi
if ! $INSTALL_AI; then
  echo "  Tip: re-run with --ai to enable the Claude AI brain"
fi
echo "═══════════════════════════════════════════════════════════════"
