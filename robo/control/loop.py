"""The async control loop — the robot's heartbeat.

Responsibilities:
  * poll sensors at a fixed rate and publish telemetry to subscribers (the UI),
  * run a reflexive safety behavior (stop before hitting things),
  * execute Command lists coming from the API or the AI brain.

This object is the single owner of the hardware, so motor commands never race.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque

from robo.brain.base import Command, Perception
from robo.brain.factory import make_brain
from robo.config import settings
from robo.hardware import Robot, make_robot
from robo.hardware.base import Telemetry
from robo.listen import STT, make_stt
from robo.listen.voice_loop import VoiceLoop
from robo.speech import make_speech
from robo.vision import Camera, make_camera

log = logging.getLogger("robo.control")

LOOP_HZ = 10
SAFE_DISTANCE_CM = 20.0  # closer than this -> no forward motion allowed


class Controller:
    def __init__(self) -> None:
        self.robot: Robot = make_robot()
        self.speech = make_speech()
        self.camera: Camera = make_camera()
        self.brain = make_brain()
        self.stt: STT = make_stt()
        self.voice = VoiceLoop(self.stt, self._on_voice)
        self.telemetry = Telemetry()
        # Rolling conversation memory (user/assistant text turns) for the brain.
        self._history: deque[dict] = deque(maxlen=8)
        self._subscribers: set[asyncio.Queue[Telemetry]] = set()
        self._lock = asyncio.Lock()  # serializes motor access
        self._running = False
        self._autonomous = False

    # --- telemetry pub/sub -------------------------------------------------
    def subscribe(self) -> asyncio.Queue[Telemetry]:
        q: asyncio.Queue[Telemetry] = asyncio.Queue(maxsize=1)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Telemetry]) -> None:
        self._subscribers.discard(q)

    def _publish(self, t: Telemetry) -> None:
        for q in self._subscribers:
            if q.full():
                _ = q.get_nowait()  # drop stale frame
            q.put_nowait(t)

    # --- main loop ---------------------------------------------------------
    async def run(self) -> None:
        self._running = True
        log.info("control loop @ %d Hz", LOOP_HZ)
        period = 1.0 / LOOP_HZ
        try:
            while self._running:
                async with self._lock:
                    self.telemetry = self.robot.read()
                    if self._autonomous:
                        self._wander(self.telemetry)
                    elif self._too_close(self.telemetry):
                        self.robot.stop()  # safety reflex
                self._publish(self.telemetry)
                await asyncio.sleep(period)
        finally:
            self.voice.stop()
            self.robot.close()
            self.camera.close()

    def stop_loop(self) -> None:
        self._running = False

    # --- camera ------------------------------------------------------------
    async def snapshot(self) -> bytes | None:
        return await self.camera.read_jpeg()

    @staticmethod
    def _too_close(t: Telemetry) -> bool:
        return t.distance_cm is not None and t.distance_cm < SAFE_DISTANCE_CM

    def _wander(self, t: Telemetry) -> None:
        """Trivial autonomous behavior: forward, turn away from obstacles."""
        if self._too_close(t):
            self.robot.turn_right(0.7)
        else:
            self.robot.forward(0.6)

    # --- command execution -------------------------------------------------
    async def execute(self, commands: list[Command]) -> None:
        for cmd in commands:
            if cmd.action == "drive":
                async with self._lock:
                    # honor the safety reflex even for manual/brain commands
                    if cmd.left + cmd.right > 0 and self._too_close(self.telemetry):
                        log.warning("blocked forward drive: obstacle %.1fcm", self.telemetry.distance_cm or -1)
                        self.robot.stop()
                    else:
                        self.robot.drive(cmd.left, cmd.right)
            elif cmd.action == "stop":
                async with self._lock:
                    self.robot.stop()
            elif cmd.action == "say":
                await self.speech.say(cmd.text)
            elif cmd.action == "wait":
                await asyncio.sleep(cmd.seconds)

    async def instruct(self, text: str, use_vision: bool | None = None) -> list[Command]:
        """Natural-language instruction -> brain -> executed commands.

        When vision is on, a fresh camera frame is attached so the brain can
        see what the robot sees. Defaults to settings.vision_default.
        """
        if use_vision is None:
            use_vision = settings.vision_default
        image = await self.camera.read_jpeg() if use_vision else None
        perception = Perception(
            instruction=text,
            telemetry=self.telemetry,
            image_jpeg=image,
            history=list(self._history),
            grab_frame=self.camera.read_jpeg,  # lets the brain `look` on demand
        )
        commands = await self.brain.decide(perception)
        await self.execute(commands)
        # Remember this exchange so follow-ups and small talk have context.
        self._history.append({"role": "user", "content": text})
        self._history.append({"role": "assistant", "content": self._summarize(commands)})
        return commands

    @staticmethod
    def _summarize(commands: list[Command]) -> str:
        """A short plain-text recap of what Robo did, for conversation memory."""
        spoken = " ".join(c.text for c in commands if c.action == "say" and c.text)
        moves = [c.action for c in commands if c.action in ("drive", "stop")]
        if spoken and moves:
            return f"{spoken} ({', '.join(moves)})"
        if spoken:
            return spoken
        return "(" + ", ".join(c.action for c in commands) + ")" if commands else "(no action)"

    def set_autonomous(self, on: bool) -> None:
        self._autonomous = on
        log.info("autonomous=%s", on)

    # --- voice -------------------------------------------------------------
    async def transcribe_file(self, path: str) -> str:
        """Transcribe a recorded audio file (browser hold-to-talk)."""
        return await self.stt.transcribe_file(path)

    async def voice_command(self, path: str) -> dict:
        """Transcribe an uploaded clip, then run it as an instruction."""
        text = await self.transcribe_file(path)
        if not text:
            return {"transcript": "", "commands": []}
        commands = await self.instruct(text)
        return {"transcript": text, "commands": [c.__dict__ for c in commands]}

    async def _on_voice(self, text: str) -> None:
        """Handler for the continuous server-side voice loop."""
        await self.instruct(text)

    def set_listening(self, on: bool) -> None:
        """Toggle the robot's own microphone (continuous listening)."""
        if on:
            self.voice.start()
        else:
            self.voice.stop()
