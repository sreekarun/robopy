"""FastAPI app: REST control + a WebSocket for live telemetry, plus the web UI.

Endpoints:
  GET  /                 -> control UI
  POST /api/drive        -> {left, right}
  POST /api/stop
  POST /api/say          -> {text}
  POST /api/instruct     -> {text}   (natural language -> brain)
  POST /api/autonomous   -> {on}
  POST /api/voice        -> audio upload: transcribe + instruct (hold-to-talk)
  POST /api/listening    -> {on}   (toggle the robot's own mic / continuous STT)
  WS   /ws/telemetry     -> stream of telemetry snapshots
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from robo.config import settings
from robo.control import Controller

log = logging.getLogger("robo.api")
WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


class DriveBody(BaseModel):
    left: float
    right: float


class SayBody(BaseModel):
    text: str


class InstructBody(BaseModel):
    text: str
    use_vision: bool | None = None


class AutonomousBody(BaseModel):
    on: bool


class ListeningBody(BaseModel):
    on: bool


def create_app() -> FastAPI:
    app = FastAPI(title="Robo")
    controller = Controller()

    @app.on_event("startup")
    async def _startup() -> None:
        app.state.loop_task = asyncio.create_task(controller.run())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        controller.stop_loop()
        app.state.loop_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await app.state.loop_task

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.post("/api/drive")
    async def drive(body: DriveBody) -> dict:
        from robo.brain.base import Command
        await controller.execute([Command("drive", left=body.left, right=body.right)])
        return {"ok": True}

    @app.post("/api/stop")
    async def stop() -> dict:
        from robo.brain.base import Command
        await controller.execute([Command("stop")])
        return {"ok": True}

    @app.post("/api/say")
    async def say(body: SayBody) -> dict:
        from robo.brain.base import Command
        await controller.execute([Command("say", text=body.text)])
        return {"ok": True}

    @app.post("/api/instruct")
    async def instruct(body: InstructBody) -> dict:
        commands = await controller.instruct(body.text, use_vision=body.use_vision)
        return {"ok": True, "commands": [c.__dict__ for c in commands]}

    @app.get("/snapshot.jpg")
    async def snapshot() -> Response:
        frame = await controller.snapshot()
        if frame is None:
            return Response(status_code=503, content=b"camera unavailable")
        return Response(content=frame, media_type="image/jpeg")

    @app.get("/stream.mjpg")
    async def stream() -> StreamingResponse:
        boundary = "frame"

        async def gen():
            async for frame in controller.camera.frames(settings.camera_fps):
                yield (
                    f"--{boundary}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(frame)}\r\n\r\n"
                ).encode() + frame + b"\r\n"

        return StreamingResponse(
            gen(),
            media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        )

    @app.post("/api/autonomous")
    async def autonomous(body: AutonomousBody) -> dict:
        controller.set_autonomous(body.on)
        return {"ok": True, "autonomous": body.on}

    @app.post("/api/voice")
    async def voice(audio: UploadFile = File(...)) -> dict:
        # Persist the browser-recorded blob, then transcribe + act on it.
        suffix = Path(audio.filename or "clip.webm").suffix or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await audio.read())
            path = tmp.name
        try:
            result = await controller.voice_command(path)
        finally:
            with contextlib.suppress(OSError):
                Path(path).unlink()
        return {"ok": True, **result}

    @app.post("/api/listening")
    async def listening(body: ListeningBody) -> dict:
        try:
            controller.set_listening(body.on)
        except Exception as exc:  # noqa: BLE001 - surface mic/dep errors to UI
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "listening": controller.voice.running}

    @app.websocket("/ws/telemetry")
    async def telemetry_ws(ws: WebSocket) -> None:
        await ws.accept()
        q = controller.subscribe()
        try:
            while True:
                t = await q.get()
                await ws.send_json(t.__dict__)
        except WebSocketDisconnect:
            pass
        finally:
            controller.unsubscribe(q)

    if WEB_DIR.exists():
        app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    app.state.controller = controller
    return app
