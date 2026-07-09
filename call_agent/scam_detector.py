"""Rule-based scam detection over YAML scenarios. Pure logic, offline."""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

import yaml


@dataclass
class Trigger:
    phrases: list[str]
    weight: int


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
        triggers = [Trigger(phrases=[p.lower() for p in t["phrases"]], weight=int(t["weight"]))
                    for t in raw["triggers"]]
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
        low = text.lower()
        hits: list[Hit] = []
        for scenario in self._scenarios:
            for trig in scenario.triggers:
                matched = next((p for p in trig.phrases if p in low), None)
                if matched is not None:
                    self._scores[scenario.key] += trig.weight
                    hits.append(Hit(scenario.key, matched, trig.weight))
        return hits

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
