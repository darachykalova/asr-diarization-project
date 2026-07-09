"""Deterministic reply selection. No NLU — keyword + verdict driven."""
from __future__ import annotations

import random
from dataclasses import dataclass

import yaml


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

    def _pick(self, key: str) -> str:
        return self._rng.choice(self._replies[key])

    def greeting(self) -> str:
        return self._pick("greeting")

    def filler(self) -> str:
        return self._pick("fillers")

    def take_message_line(self) -> str:
        return self._pick("take_message")

    def on_caller_utterance(self, text: str, verdict: str) -> Reply:
        if verdict == "scam":
            return Reply(text="", kind="hangup", hang_up=True)
        return Reply(text=self._pick("keep_talking"), kind="talk", hang_up=False)
