"""Keyword brain — works with zero dependencies and no API key.

Lets you exercise the whole command pipeline today. Replaced by ClaudeBrain
when you enable the AI extra.
"""
from __future__ import annotations

from robo.brain.base import Brain, Command, Perception


class NullBrain(Brain):
    async def decide(self, perception: Perception) -> list[Command]:
        text = perception.instruction.lower()
        # A little small talk so the keyword brain isn't stone-faced. (Real
        # conversation and multi-step understanding need ClaudeBrain.)
        if any(g in text for g in ("hello", "hi ", "hey", "hi!")) or text in ("hi", "hey"):
            return [Command("say", text="Hi! I'm Robo. Tell me where to go.")]
        if "your name" in text or "who are you" in text:
            return [Command("say", text="I'm Robo, your little robot.")]
        if "how are you" in text:
            return [Command("say", text="Running smoothly, thanks for asking!")]
        if "thank" in text:
            return [Command("say", text="You're welcome!")]
        if "forward" in text or "go" in text:
            return [Command("say", text="Moving forward"), Command("drive", left=0.8, right=0.8)]
        if "back" in text:
            return [Command("drive", left=-0.8, right=-0.8)]
        if "left" in text:
            return [Command("drive", left=-0.7, right=0.7)]
        if "right" in text:
            return [Command("drive", left=0.7, right=-0.7)]
        if "stop" in text:
            return [Command("stop"), Command("say", text="Stopping")]
        return [Command("say", text="I only know simple commands right now — "
                                    "turn on the AI brain so I can really chat.")]
