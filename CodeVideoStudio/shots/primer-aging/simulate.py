"""Agent-based model of the evolution of aging, for the Primer-style film.

Two environments (dangerous / safer) run for the same number of steps.  Each
agent carries late-acting deleterious mutations (mutation accumulation) and
pleiotropic alleles that help early reproduction but add late hazard
(antagonistic pleiotropy).  The output is a deterministic film track consumed
by ``main.js``.

    python simulate.py --out aging.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

STEPS = 420
RECORD_EVERY = 2
MATURITY = 10
MAX_AGE = 90
CAPACITY = 190
FIELD_X = 6.8
FIELD_Y = 4.2
P_MA = 0.22
P_AP = 0.040
MAX_MA = 80
MAX_AP = 10


class Agent:
    __slots__ = ("x", "y", "age", "alive", "ma", "ap", "dx", "dy")

    def __init__(self, x: float, y: float, age: int, ma=None, ap=None):
        self.x = x
        self.y = y
        self.age = age
        self.alive = True
        self.ma = ma or []  # (onset, effect)
        self.ap = ap or []  # (bonus, onset, hazard)
        self.dx = 0.0
        self.dy = 0.0


def birth_bonus(agent: Agent) -> float:
    return sum(bonus for bonus, _, _ in agent.ap)


def hazard(agent: Agent, extrinsic: float) -> float:
    value = extrinsic
    for onset, effect in agent.ma:
        if agent.age >= onset:
            value += effect
    for _, onset, effect in agent.ap:
        if agent.age >= onset:
            value += effect
    return value


def spawn(rng: random.Random, x: float, y: float, age: int, ma, ap) -> Agent:
    child = Agent(x, y, age, list(ma), list(ap))
    if len(child.ma) < MAX_MA and rng.random() < P_MA:
        child.ma.append((rng.randint(0, MAX_AGE), rng.uniform(0.004, 0.014)))
    if len(child.ap) < MAX_AP and rng.random() < P_AP:
        child.ap.append((rng.uniform(0.15, 0.35), MATURITY, rng.uniform(0.010, 0.020)))
    return child


def run(extrinsic: float, seed: int) -> dict:
    rng = random.Random(seed)
    agents = [
        Agent(rng.uniform(-FIELD_X, FIELD_X), rng.uniform(-FIELD_Y, FIELD_Y), rng.randint(0, 16))
        for _ in range(130)
    ]
    roster: list[Agent] = list(agents)
    frames = []
    deaths: list[int] = []
    exposed = [0] * (MAX_AGE + 1)
    died = [0] * (MAX_AGE + 1)
    born_total = 0

    for step in range(STEPS):
        next_generation = []
        for agent in agents:
            if not agent.alive:
                continue
            if agent.age <= MAX_AGE:
                exposed[agent.age] += 1
            if rng.random() > math.exp(-hazard(agent, extrinsic)):
                agent.alive = False
                deaths.append(agent.age)
                if agent.age <= MAX_AGE:
                    died[agent.age] += 1
                continue
            if MATURITY <= agent.age <= 70 and len(agents) + len(next_generation) < CAPACITY:
                chance = 0.110 * (1.0 + birth_bonus(agent))
                if rng.random() < chance:
                    cx = min(FIELD_X, max(-FIELD_X, agent.x + rng.gauss(0, 0.7)))
                    cy = min(FIELD_Y, max(-FIELD_Y, agent.y + rng.gauss(0, 0.5)))
                    next_generation.append(spawn(rng, cx, cy, 0, agent.ma, agent.ap))
                    born_total += 1
            agent.age += 1
            agent.dx = 0.85 * agent.dx + rng.gauss(0, 0.22)
            agent.dy = 0.85 * agent.dy + rng.gauss(0, 0.18)
            pull = 0.004
            agent.x = min(FIELD_X, max(-FIELD_X, agent.x + agent.dx - pull * agent.x))
            agent.y = min(FIELD_Y, max(-FIELD_Y, agent.y + agent.dy - pull * agent.y))

        agents = [agent for agent in agents if agent.alive] + next_generation
        roster.extend(next_generation)

        if step % RECORD_EVERY == 0:
            frames.append(
                {
                    "born": born_total,
                    "agents": [
                        [
                            round(agent.x, 3),
                            round(agent.y, 3),
                            agent.age,
                            1 if agent.alive else 0,
                            len(agent.ma),
                            len(agent.ap),
                        ]
                        for agent in roster[-CAPACITY:]
                    ],
                    "population": len(agents),
                    "mean_death_age": round(sum(deaths[-80:]) / max(1, len(deaths[-80:])), 2)
                    if deaths
                    else None,
                    "hazard": [
                        round(died[age] / exposed[age], 4) if exposed[age] else None
                        for age in range(MAX_AGE + 1)
                    ],
                }
            )

    final_agents = [agent for agent in agents if agent.alive]
    mean_ma = sum(len(agent.ma) for agent in final_agents) / max(1, len(final_agents))
    mean_ap = sum(len(agent.ap) for agent in final_agents) / max(1, len(final_agents))
    return {
        "extrinsic": extrinsic,
        "frames": frames,
        "summary": {
            "population": len(final_agents),
            "mean_death_age": round(sum(deaths[-160:]) / max(1, len(deaths[-160:])), 2)
            if deaths
            else None,
            "mean_ma_loci": round(mean_ma, 2),
            "mean_ap_loci": round(mean_ap, 2),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="aging.json")
    args = parser.parse_args()
    payload = {
        "schema_version": 1,
        "fps": 30,
        "steps": STEPS,
        "record_every": RECORD_EVERY,
        "maturity": MATURITY,
        "scenarios": [
            {"id": "danger", "label": "dangerous world", "mu": 0.030, **run(0.030, seed=7)},
            {"id": "safe", "label": "safer world", "mu": 0.008, **run(0.008, seed=11)},
        ],
    }
    target = Path(args.out)
    target.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {target} ({target.stat().st_size / 1e6:.1f} MB)")
    for scenario in payload["scenarios"]:
        print(scenario["id"], scenario["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
