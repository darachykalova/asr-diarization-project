"""Rule-based scam detection over YAML scenarios. Pure logic, offline."""
from __future__ import annotations

import glob
import os
import re
from dataclasses import dataclass, field

import yaml

_WORD_RE = re.compile(r"[а-яёa-z0-9]+")


def _normalize(text: str) -> str:
    return text.lower().replace("ё", "е")


@dataclass
class Trigger:
    phrases: list[str] = field(default_factory=list)
    stems: list[str] = field(default_factory=list)
    weight: int = 0


@dataclass
class Scenario:
    key: str
    name: str
    threshold: int
    triggers: list[Trigger]


@dataclass
class Hit:
    scenario_key: str
    phrase: str
    weight: int


def load_scenarios(dir_path: str) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(glob.glob(os.path.join(dir_path, "*.yaml"))):
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        triggers = []
        for t in raw["triggers"]:
            phrases = [_normalize(p) for p in t.get("phrases", [])]
            stems = [_normalize(s) for s in t.get("stems", [])]
            if not phrases and not stems:
                raise ValueError(f"{path}: trigger has neither phrases nor stems")
            triggers.append(Trigger(phrases=phrases, stems=stems, weight=int(t["weight"])))
        scenarios.append(Scenario(
            key=raw["key"], name=raw["name"],
            threshold=int(raw["threshold"]), triggers=triggers,
        ))
    return scenarios


class ScamDetector:
    def __init__(self, scenarios: list[Scenario]):
        self._scenarios = scenarios
        self._scores: dict[str, int] = {s.key: 0 for s in scenarios}

    def feed(self, text: str) -> list[Hit]:
        low = _normalize(text)
        tokens = _WORD_RE.findall(low)
        hits: list[Hit] = []
        for scenario in self._scenarios:
            for trig in scenario.triggers:
                matched = next((p for p in trig.phrases if p in low), None)
                if matched is None and trig.stems:
                    if all(any(tok.startswith(stem) for tok in tokens)
                           for stem in trig.stems):
                        matched = "+".join(trig.stems)
                if matched is not None:
                    self._scores[scenario.key] += trig.weight
                    hits.append(Hit(scenario.key, matched, trig.weight))
        return hits

    def leading_score(self) -> tuple[str | None, int, int]:
        best_key, best_score, best_threshold = None, 0, 0
        for scenario in self._scenarios:
            score = self._scores[scenario.key]
            if score > best_score:
                best_key, best_score, best_threshold = scenario.key, score, scenario.threshold
        return (best_key, best_score, best_threshold)

    def total_delta_for(self, text: str) -> int:
        return sum(h.weight for h in self.feed(text))

    def verdict(self) -> tuple[str, str | None, int]:
        best_key, best_conf = None, 0
        for scenario in self._scenarios:
            score = self._scores[scenario.key]
            if score >= scenario.threshold:
                conf = min(100, round(score / scenario.threshold * 100))
                if conf > best_conf or (conf == best_conf and best_key is None):
                    best_key, best_conf = scenario.key, conf
        if best_key is None:
            return ("undetermined", None, 0)
        return ("scam", best_key, best_conf)
