"""Pipeline state manager for CourseWorkspace (Automotive Aerodynamics).

Implements:
1. symbol_registry: Single Source of Truth for physical symbols and LaTeX formulas.
2. covered_ledger: Cumulative knowledge ledger to prevent cross-lecture repetition.
3. forward_guard: Lock forward concepts to prevent early spoilers.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class SymbolEntry:
    symbol_id: str
    latex_repr: str
    canonical_en: str
    canonical_zh: str
    standard_unit: str
    first_introduced_lesson: str
    allowed_variants: list[str]


@dataclass
class LedgerEntry:
    atom_id: str
    lesson_id: str
    concept_title: str
    key_conclusion_en: str
    key_conclusion_zh: str
    equation_refs: list[str]
    case_studies_used: list[str]


class PipelineStateDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        with self.conn:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_registry (
                symbol_id TEXT PRIMARY KEY,
                latex_repr TEXT NOT NULL,
                canonical_en TEXT NOT NULL,
                canonical_zh TEXT NOT NULL,
                standard_unit TEXT,
                first_introduced_lesson TEXT,
                allowed_variants TEXT
            );
            """)
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS covered_ledger (
                atom_id TEXT PRIMARY KEY,
                lesson_id TEXT NOT NULL,
                concept_title TEXT NOT NULL,
                key_conclusion_en TEXT NOT NULL,
                key_conclusion_zh TEXT NOT NULL,
                equation_refs TEXT,
                case_studies_used TEXT
            );
            """)
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS forward_guard (
                concept_id TEXT PRIMARY KEY,
                planned_lesson_id TEXT NOT NULL,
                forbidden_terms TEXT NOT NULL
            );
            """)

    def register_symbol(self, entry: SymbolEntry) -> None:
        with self.conn:
            self.conn.execute("""
            INSERT OR REPLACE INTO symbol_registry 
            (symbol_id, latex_repr, canonical_en, canonical_zh, standard_unit, first_introduced_lesson, allowed_variants)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                entry.symbol_id,
                entry.latex_repr,
                entry.canonical_en,
                entry.canonical_zh,
                entry.standard_unit,
                entry.first_introduced_lesson,
                json.dumps(entry.allowed_variants, ensure_ascii=False)
            ))

    def record_covered(self, entry: LedgerEntry) -> None:
        with self.conn:
            self.conn.execute("""
            INSERT OR REPLACE INTO covered_ledger
            (atom_id, lesson_id, concept_title, key_conclusion_en, key_conclusion_zh, equation_refs, case_studies_used)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                entry.atom_id,
                entry.lesson_id,
                entry.concept_title,
                entry.key_conclusion_en,
                entry.key_conclusion_zh,
                json.dumps(entry.equation_refs, ensure_ascii=False),
                json.dumps(entry.case_studies_used, ensure_ascii=False)
            ))

    def get_symbols_for_lesson(self, latex_text: str) -> list[dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM symbol_registry")
        matched = []
        for row in cursor.fetchall():
            latex_repr = row["latex_repr"]
            if latex_repr in latex_text:
                matched.append(dict(row))
        return matched

    def get_covered_ledger_up_to(self, lesson_index: int) -> list[dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM covered_ledger ORDER BY lesson_id ASC")
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()


def seed_standard_aerodynamics_symbols(db: PipelineStateDB) -> None:
    """Seed foundational physical symbols for the aerodynamics curriculum."""
    standard_symbols = [
        SymbolEntry("rho", r"\rho", "Fluid density", "流体密度", "kg/m^3", "T1-02", [r"\rho_\infty"]),
        SymbolEntry("v_inf", r"v_\infty", "Freestream velocity", "来流速度", "m/s", "T1-02", [r"U_\infty", r"V_\infty"]),
        SymbolEntry("mu", r"\mu", "Dynamic viscosity", "动力粘度", "Pa*s", "T2-05", []),
        SymbolEntry("nu", r"\nu", "Kinematic viscosity", "运动粘度", "m^2/s", "T2-05", []),
        SymbolEntry("p", r"p", "Static pressure", "静压", "Pa", "T2-03", [r"p_\infty", r"p_0"]),
        SymbolEntry("c_p", r"c_p", "Pressure coefficient", "压力系数", "-", "T2-06", [r"C_p", r"C_{pb}"]),
        SymbolEntry("c_d", r"c_D", "Aerodynamic drag coefficient", "气动阻力系数", "-", "T1-02", [r"C_d", r"C_D"]),
        SymbolEntry("c_l", r"c_L", "Aerodynamic lift coefficient", "气动升力系数", "-", "T4-01", [r"C_l", r"C_L"]),
        SymbolEntry("c_s", r"c_S", "Side force coefficient", "侧向力系数", "-", "T4-01", [r"C_Y"]),
        SymbolEntry("re", r"Re", "Reynolds number", "雷诺数", "-", "T1-01", [r"Re_L", r"Re_x"]),
        SymbolEntry("ma", r"Ma", "Mach number", "马赫数", "-", "T2-01", [r"M"]),
        SymbolEntry("delta", r"\delta", "Boundary layer physical thickness", "边界层名义厚度", "m", "T2-14", [r"\delta_{99}"]),
        SymbolEntry("delta_star", r"\delta^*", "Displacement thickness", "排挤厚度", "m", "T2-16", [r"\delta_1"]),
        SymbolEntry("theta", r"\theta", "Momentum thickness", "动量损失厚度", "m", "T2-16", [r"\delta_2"]),
        SymbolEntry("tau_w", r"\tau_w", "Wall shear stress", "壁面剪切应力", "Pa", "T2-16", []),
        SymbolEntry("c_f", r"c_f", "Skin friction coefficient", "表面摩擦阻力系数", "-", "T2-16", [r"C_f"]),
        SymbolEntry("omega", r"\vec{\omega}", "Vorticity vector", "涡量矢量", "1/s", "T2-12", [r"\omega"]),
        SymbolEntry("gamma", r"\Gamma", "Circulation", "环量", "m^2/s", "T2-11", []),
        SymbolEntry("y_plus", r"y^+", "Dimensionless wall distance", "无量纲壁面距离", "-", "T14-10", []),
        SymbolEntry("k_turb", r"k", "Turbulent kinetic energy", "湍流动能", "m^2/s^2", "T14-08", []),
        SymbolEntry("epsilon_turb", r"\varepsilon", "Turbulence dissipation rate", "湍流耗散率", "m^2/s^3", "T14-08", []),
        SymbolEntry("omega_turb", r"\omega", "Specific turbulence dissipation rate", "比耗散率", "1/s", "T14-09", []),
    ]
    for sym in standard_symbols:
        db.register_symbol(sym)


if __name__ == "__main__":
    db_file = Path("shared/state/aerodynamics_pipeline.db")
    db = PipelineStateDB(db_file)
    seed_standard_aerodynamics_symbols(db)
    print(f"Successfully initialized pipeline state DB at {db_file}")
    db.close()
