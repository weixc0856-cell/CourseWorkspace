"""Deterministic agent-simulation contract and runner.

The contract is engine-agnostic: Blender and CodeVideoStudio both consume the
same ``SimulationData`` (cells, per-frame species, fractions).
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from course_control.content.contracts import StrictModel

HEX = r"^#[0-9A-Fa-f]{6}$"
NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))


class Species(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,31}$")
    name: str = Field(min_length=1)
    hex: str = Field(pattern=HEX)


class HexGrid(StrictModel):
    kind: Literal["hex"] = "hex"
    radius: int = Field(default=5, ge=1, le=20)


class RPSRules(StrictModel):
    kind: Literal["rock_paper_scissors"] = "rock_paper_scissors"
    matrix: list[list[float]]
    mutation: float = Field(default=1e-4, ge=0.0, le=0.1)
    updates_per_frame: int = Field(default=8, ge=1, le=64)

    @model_validator(mode="after")
    def _matrix_shape(self):
        if len(self.matrix) != 3 or any(len(row) != 3 for row in self.matrix):
            raise ValueError("matrix must be 3x3")
        if any(value < 0 or value > 10 for row in self.matrix for value in row):
            raise ValueError("matrix values must be between 0 and 10")
        return self


class SimulationSpec(StrictModel):
    schema_version: Literal[1] = 1
    simulation_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    title: str = Field(min_length=1)
    seed: int = Field(ge=0)
    grid: HexGrid = Field(default_factory=HexGrid)
    species: list[Species] = Field(min_length=3, max_length=3)
    rules: RPSRules
    frames: int = Field(default=900, ge=1, le=100000)
    fps: int = Field(default=30, ge=1, le=120)

    @model_validator(mode="after")
    def _unique_species(self):
        ids = [item.id for item in self.species]
        if len(ids) != len(set(ids)):
            raise ValueError("species ids must be unique")
        return self


class SimulationCell(StrictModel):
    q: int
    r: int
    x: float
    y: float


class SimulationData(StrictModel):
    schema_version: Literal[1] = 1
    simulation_id: str
    title: str
    seed: int
    fps: int
    frames: int
    updates_per_frame: int
    mutation: float
    matrix: list[list[float]]
    species: list[Species]
    cells: list[SimulationCell]
    frames_species: list[list[int]]
    fractions: list[list[float]]


def hex_cells(radius: int) -> list[SimulationCell]:
    cells: list[SimulationCell] = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if abs(q + r) > radius:
                continue
            cells.append(
                SimulationCell(
                    q=q,
                    r=r,
                    x=round(1.5 * q, 4),
                    y=round(math.sqrt(3) * (r + q / 2), 4),
                )
            )
    return cells


def run_simulation(spec: SimulationSpec) -> SimulationData:
    rng = random.Random(spec.seed)
    cells = hex_cells(spec.grid.radius)
    index = {(cell.q, cell.r): position for position, cell in enumerate(cells)}
    neighbours = [
        [
            index[(cell.q + dq, cell.r + dr)]
            for dq, dr in NEIGHBORS
            if (cell.q + dq, cell.r + dr) in index
        ]
        for cell in cells
    ]
    matrix = spec.rules.matrix
    species = [rng.randrange(3) for _ in cells]
    frames: list[list[int]] = []
    fractions: list[list[float]] = []
    for _ in range(spec.frames):
        for _ in range(spec.rules.updates_per_frame):
            i = rng.randrange(len(species))
            j = rng.choice(neighbours[i])
            if matrix[species[i]][species[j]] < matrix[species[j]][species[i]]:
                species[i] = species[j]
            if rng.random() < spec.rules.mutation:
                species[i] = rng.randrange(3)
        frames.append(list(species))
        counts = [species.count(k) for k in range(3)]
        total = sum(counts)
        fractions.append([round(counts[k] / total, 6) for k in range(3)])
    return SimulationData(
        simulation_id=spec.simulation_id,
        title=spec.title,
        seed=spec.seed,
        fps=spec.fps,
        frames=spec.frames,
        updates_per_frame=spec.rules.updates_per_frame,
        mutation=spec.rules.mutation,
        matrix=matrix,
        species=spec.species,
        cells=cells,
        frames_species=frames,
        fractions=fractions,
    )


def load_spec(path: Path) -> SimulationSpec:
    return SimulationSpec.model_validate_json(path.read_text(encoding="utf-8"))


def write_data(data: SimulationData, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data.model_dump(mode="json"), separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def write_spec(spec: SimulationSpec, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(spec.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path
