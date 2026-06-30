"""Claude-powered brain (enable with the `ai` extra: pip install '.[ai]').

This is the supercharge path. Claude receives the instruction, the live
telemetry, and — once vision is wired — a camera frame, then calls robot
'tools' (drive/stop/say/wait). Tool-use maps cleanly onto our Command objects,
so the model literally decides how the robot moves.

Set ROBO_BRAIN_ENABLED=true and ANTHROPIC_API_KEY=... to turn it on.
"""
from __future__ import annotations

import base64
import json
import logging

from robo.brain.base import Brain, Command, Perception
from robo.config import settings

log = logging.getLogger("robo.brain.claude")

SYSTEM = (
    "You are Robo, a small, friendly differential-drive robot. You can move "
    "around AND hold a conversation. Each message is the person talking to you, "
    "along with your live sensor telemetry and sometimes a camera image. The "
    "earlier messages are your recent conversation — use them for context "
    "(follow-ups like 'do that again', remembering what was just said). Always "
    "reply by calling tools.\n"
    "\n"
    "TALKING — for greetings, questions, jokes, thanks, or any chit-chat, just "
    "call `say` with a short, warm, in-character reply and do NOT move. Your "
    "name is Robo. You can answer about yourself, what the camera shows, or your "
    "sensor readings (distance, light, motion). One or two sentences, max.\n"
    "\n"
    "MOVING — when asked to move, call `drive`. Motor speeds are -1.0 (full "
    "reverse) to 1.0 (full forward); left and right are the two tracks (to turn "
    "in place, drive them opposite). For a multi-step request ('go forward then "
    "turn left'), emit the tools in order: drive, a `wait` for that move's "
    "duration, the next drive, and so on. A drive runs until the next command "
    "changes it, so always follow a drive with a wait and end a motion sequence "
    "with a `stop`. You may `say` a short line first.\n"
    "\n"
    "SEEING — you have a camera. To see what's actually in front of you — to "
    "identify objects, find something, read a label, or check a scene — call "
    "`look`. You'll get the current image back; then identify what you see and "
    "describe it with `say`. Don't guess about the world without looking first.\n"
    "\n"
    "SAFETY — never drive forward when distance_cm is small (obstacle ahead); "
    "say so instead.\n"
    "Always respond with at least one tool call."
)

# Tool schema — each tool is one robot Command.
TOOLS = [
    {
        "name": "drive",
        "description": "Set left and right motor speeds, each -1.0..1.0.",
        "input_schema": {
            "type": "object",
            "properties": {
                "left": {"type": "number"},
                "right": {"type": "number"},
            },
            "required": ["left", "right"],
        },
    },
    {
        "name": "stop",
        "description": "Stop both motors immediately.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "say",
        "description": "Speak a short phrase out loud.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "wait",
        "description": "Pause for some seconds before the next command.",
        "input_schema": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"],
        },
    },
    {
        "name": "look",
        "description": (
            "Look through your camera to see what is in front of you right now. "
            "Call this whenever the user asks what you see, asks you to identify "
            "or find an object, or before acting on something visual. You'll get "
            "the current image back, then describe what you see with `say`."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]

# How many look round-trips to allow per decision (avoids loops).
MAX_LOOKS = 2


class ClaudeBrain(Brain):
    def __init__(self) -> None:
        from anthropic import AsyncAnthropic  # lazy: only needed when enabled

        # Prefer ROBO_ANTHROPIC_API_KEY; otherwise let the SDK resolve creds from
        # the environment (ANTHROPIC_API_KEY) or an `ant auth login` profile.
        if settings.anthropic_api_key:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            self._client = AsyncAnthropic()
        self._model = settings.brain_model
        log.info("ClaudeBrain ready (model=%s effort=%s)", self._model, settings.brain_effort)

    @staticmethod
    def _image_block(jpeg: bytes) -> dict:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.b64encode(jpeg).decode(),
            },
        }

    def _content(self, p: Perception) -> list[dict]:
        blocks: list[dict] = [
            {
                "type": "text",
                "text": (
                    f"Instruction: {p.instruction}\n"
                    f"Telemetry: {json.dumps(p.telemetry.__dict__)}"
                ),
            }
        ]
        if p.image_jpeg is not None:
            blocks.append(self._image_block(p.image_jpeg))
        return blocks

    async def _create(self, messages: list[dict]):
        return await self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=SYSTEM,
            tools=TOOLS,
            tool_choice={"type": "any"},
            # Low effort keeps the control loop responsive; bump via ROBO_BRAIN_EFFORT.
            output_config={"effort": settings.brain_effort},
            messages=messages,
        )

    async def decide(self, perception: Perception) -> list[Command]:
        # Prior turns give conversational context; the current turn carries
        # telemetry and any pre-attached image.
        messages = list(perception.history) + [
            {"role": "user", "content": self._content(perception)}
        ]
        # Agentic loop: if the model calls `look`, feed it a fresh camera frame
        # and ask again, so it can identify what it actually sees.
        for _ in range(MAX_LOOKS + 1):
            resp = await self._create(messages)
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            looks = [b for b in tool_uses if b.name == "look"]
            if not looks:
                return self._commands(tool_uses)

            messages.append({"role": "assistant", "content": resp.content})
            frame = await perception.grab_frame() if perception.grab_frame else None
            results = []
            for b in tool_uses:
                if b.name == "look":
                    if frame is not None:
                        results.append({"type": "tool_result", "tool_use_id": b.id,
                                        "content": [self._image_block(frame)]})
                    else:
                        results.append({"type": "tool_result", "tool_use_id": b.id,
                                        "content": "Camera unavailable.", "is_error": True})
                else:  # defer any movement chosen before looking — re-decide after
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": "Noted — decide after looking."})
            messages.append({"role": "user", "content": results})

        # Exhausted look budget — return whatever non-look tools were last chosen.
        return self._commands([b for b in tool_uses if b.name != "look"])

    @staticmethod
    def _commands(tool_uses) -> list[Command]:
        commands: list[Command] = []
        for block in tool_uses:
            args = block.input
            if block.name == "drive":
                commands.append(Command("drive", left=float(args.get("left", 0)), right=float(args.get("right", 0))))
            elif block.name == "stop":
                commands.append(Command("stop"))
            elif block.name == "say":
                commands.append(Command("say", text=str(args.get("text", ""))))
            elif block.name == "wait":
                commands.append(Command("wait", seconds=float(args.get("seconds", 0))))
        return commands
