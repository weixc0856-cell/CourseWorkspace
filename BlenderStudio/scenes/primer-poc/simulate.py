"""Rock-paper-scissors agent simulation on a hexagonal grid.

Deterministic (seeded) and engine-agnostic. Writes the per-frame species grid
and species fractions consumed by the Blender world and the Remotion overlay.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

SPECIES = [
    {"name": "Rock", "hex": "#C75B55"},
    {"name": "Paper", "hex": "#E3C84A"},
    {"name": "Scissors", "hex": "#4A82B8"},
]
# score of row species against column species
MATRIX = [
    [0.5, 0.0, 1.0],
    [1.0, 0.5, 0.0],
    [0.0, 1.0, 0.5],
]
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))


def hex_cells(radius: int) -> list[dict]:
    cells = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if abs(q + r) > radius:
                continue
            x = 1.5 * q
            y = math.sqrt(3) * (r + q / 2)
            cells.append({"q": q, "r": r, "x": round(x, 4), "y": round(y, 4)})
    return cells


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--radius", type=int, default=5)
    parser.add_argument("--frames", type=int, default=900)
    parser.add_argument("--updates", type=int, default=8)
    parser.add_argument("--mutation", type=float, default=1e-4)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    cells = hex_cells(args.radius)
    index = {(cell["q"], cell["r"]): i for i, cell in enumerate(cells)}
    neighbours = [
        [index[(cell["q"] + dq, cell["r"] + dr)] for dq, dr in NEIGHBORS if (cell["q"] + dq, cell["r"] + dr) in index]
        for cell in cells
    ]
    species = [rng.randrange(3) for _ in cells]
    frames = []
    fractions = []
    for frame in range(args.frames):
        for _ in range(args.updates):
            i = rng.randrange(len(species))
            j = rng.choice(neighbours[i])
            if MATRIX[species[i]][species[j]] < MATRIX[species[j]][species[i]]:
                species[i] = species[j]
            if rng.random() < args.mutation:
                species[i] = rng.randrange(3)
        frames.append(list(species))
        counts = [species.count(k) for k in range(3)]
        total = sum(counts)
        fractions.append([round(counts[k] / total, 6) for k in range(3)])

    payload = {
        "seed": args.seed,
        "radius": args.radius,
        "frames": args.frames,
        "fps": 30,
        "updates_per_frame": args.updates,
        "mutation": args.mutation,
        "matrix": MATRIX,
        "species": SPECIES,
        "cells": cells,
        "frames_species": frames,
        "fractions": fractions,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"cells={len(cells)} frames={args.frames} out={args.out}")
    print("fraction range", [ (round(min(f[k] for f in fractions),3), round(max(f[k] for f in fractions),3)) for k in range(3) ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
