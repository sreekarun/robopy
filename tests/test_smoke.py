"""Smoke tests — run on any machine, no hardware. `pytest`"""
import asyncio

from robo.brain.base import Command, Perception
from robo.brain.null_brain import NullBrain
from robo.hardware.fake import FakeRobot
from robo.vision.fake import FakeCamera


def test_fake_robot_drives_and_reads():
    bot = FakeRobot()
    bot.forward(0.5)
    t = bot.read()
    assert t.left_speed == 0.5 and t.right_speed == 0.5
    assert t.distance_cm is not None
    bot.stop()
    assert bot.read().left_speed == 0.0


def test_null_brain_parses_commands():
    brain = NullBrain()
    cmds = asyncio.run(brain.decide(Perception("go forward", FakeRobot().read())))
    assert any(c.action == "drive" and c.left > 0 for c in cmds)

    stop = asyncio.run(brain.decide(Perception("stop now", FakeRobot().read())))
    assert any(c.action == "stop" for c in stop)


def test_fake_camera_produces_jpeg():
    frame = asyncio.run(FakeCamera().read_jpeg())
    assert frame is not None
    assert frame[:2] == b"\xff\xd8"  # JPEG SOI marker


def test_claude_brain_parses_tool_calls(monkeypatch):
    """Mock the API response; verify tool_use blocks map to Commands in order."""
    from robo.config import settings
    settings.anthropic_api_key = "sk-ant-dummy"  # avoids a real network call
    from robo.brain.claude_brain import ClaudeBrain

    brain = ClaudeBrain()

    class Block:
        def __init__(self, name, inp):
            self.type, self.name, self.input = "tool_use", name, inp

    class Resp:
        content = [
            Block("say", {"text": "Moving forward"}),
            Block("drive", {"left": 0.8, "right": 0.8}),
            Block("wait", {"seconds": 1.0}),
            Block("drive", {"left": -0.7, "right": 0.7}),
            Block("stop", {}),
        ]

    async def fake_create(**kwargs):
        assert kwargs["tool_choice"] == {"type": "any"}
        return Resp()

    brain._client.messages.create = fake_create

    cmds = asyncio.run(brain.decide(Perception("go forward then turn left", FakeRobot().read())))
    assert [c.action for c in cmds] == ["say", "drive", "wait", "drive", "stop"]
    assert cmds[1].left == 0.8 and cmds[3].left == -0.7
    settings.anthropic_api_key = None


def test_claude_brain_sends_history(monkeypatch):
    """Prior turns are prepended as messages so small talk / follow-ups have context."""
    from robo.config import settings
    settings.anthropic_api_key = "sk-ant-dummy"
    from robo.brain.claude_brain import ClaudeBrain

    brain = ClaudeBrain()
    captured = {}

    class Block:
        type, name, input = "tool_use", "say", {"text": "Hi there!"}

    class Resp:
        content = [Block()]

    async def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return Resp()

    brain._client.messages.create = fake_create

    history = [
        {"role": "user", "content": "what's your name?"},
        {"role": "assistant", "content": "I'm Robo."},
    ]
    p = Perception("nice to meet you", FakeRobot().read(), history=history)
    cmds = asyncio.run(brain.decide(p))
    # history precedes the current turn; current user message is last
    assert captured["messages"][:2] == history
    assert captured["messages"][-1]["role"] == "user"
    assert cmds[0].action == "say"
    settings.anthropic_api_key = None


def test_claude_brain_look_loop():
    """`look` triggers a frame grab, then the model describes what it sees."""
    from robo.config import settings
    settings.anthropic_api_key = "sk-ant-dummy"
    from robo.brain.claude_brain import ClaudeBrain

    brain = ClaudeBrain()
    calls = {"n": 0, "grabbed": 0}

    class TU:
        def __init__(self, name, inp, id="t1"):
            self.type, self.name, self.input, self.id = "tool_use", name, inp, id

    class Resp:
        def __init__(self, content):
            self.content = content

    async def fake_create(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return Resp([TU("look", {})])              # first: ask to look
        # second call must have received the image in a tool_result
        assert any(m["role"] == "user" and isinstance(m["content"], list)
                   and m["content"][0].get("type") == "tool_result"
                   for m in messages)
        return Resp([TU("say", {"text": "I see a blue ball."})])

    async def fake_grab():
        calls["grabbed"] += 1
        return b"\xff\xd8fakejpeg"

    brain._create = fake_create
    p = Perception("what do you see?", FakeRobot().read(), grab_frame=fake_grab)
    cmds = asyncio.run(brain.decide(p))
    assert calls["grabbed"] == 1 and calls["n"] == 2
    assert cmds[0].action == "say" and "ball" in cmds[0].text
    settings.anthropic_api_key = None


def test_null_brain_small_talk():
    brain = NullBrain()
    greet = asyncio.run(brain.decide(Perception("hello there", FakeRobot().read())))
    assert greet[0].action == "say" and "Robo" in greet[0].text


def test_fake_stt_returns_text():
    from robo.listen.fake import FakeSTT

    stt = FakeSTT("turn left")
    assert asyncio.run(stt.transcribe_file("ignored.wav")) == "turn left"


def test_voice_loop_wake_word():
    from robo.listen.fake import FakeSTT
    from robo.listen.voice_loop import VoiceLoop
    from robo.config import settings

    async def noop(_text):
        return None

    loop = VoiceLoop(FakeSTT(), noop)
    settings.wake_word = "robo"
    try:
        assert loop._matches_wake_word("robo go forward") == "go forward"
        assert loop._matches_wake_word("just chatting") is None
    finally:
        settings.wake_word = ""
