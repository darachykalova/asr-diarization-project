"""Deterministic reply selection. No NLU — keyword + verdict driven."""
from __future__ import annotations

import random
from dataclasses import dataclass

import yaml

# Простые слова приветствия — если звонящий только поздоровался (и это не
# совпало ни с одним сценарием мошенничества), отвечаем по-человечески,
# а не тяни-время фразой из keep_talking.
_GREETING_WORDS = (
    "здравствуйте", "здравствуй", "добрый день", "добрый вечер",
    "доброе утро", "приветствую", "привет",
)


def _is_greeting(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in _GREETING_WORDS)


@dataclass
class Reply:
    text: str
    kind: str      # "talk" | "hangup"
    hang_up: bool


def load_replies(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


class DialogEngine:
    def __init__(self, replies: dict, rng: random.Random | None = None):
        self._replies = replies
        self._rng = rng or random.Random()
        self._last: dict[str, str] = {}

    def _pick(self, key: str) -> str:
        options = self._replies[key]
        last = self._last.get(key)
        candidates = [o for o in options if o != last] or options
        choice = self._rng.choice(candidates)
        self._last[key] = choice
        return choice

    def greeting(self) -> str:
        return self._pick("greeting")

    def filler(self) -> str:
        return self._pick("fillers")

    def take_message_line(self) -> str:
        return self._pick("take_message")

    def before_hangup_line(self) -> str:
        return self._pick("before_hangup")

    def on_caller_utterance(self, text: str, verdict: str, has_scenario_hit: bool = False) -> Reply:
        if verdict == "scam":
            return Reply(text="", kind="hangup", hang_up=True)
        if not has_scenario_hit and _is_greeting(text):
            return Reply(text=self._pick("greeting_reply"), kind="talk", hang_up=False)
        return Reply(text=self._pick("keep_talking"), kind="talk", hang_up=False)
