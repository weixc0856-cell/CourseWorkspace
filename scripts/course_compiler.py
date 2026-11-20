"""Course Compiler Engine for 180-Episode Aerodynamics Curriculum.

Orchestrates:
1. Dynamic Prompt Assembly with Symbol Bible (symbol_registry) and Cumulative Ledger (covered_ledger).
2. Four-Step Pedagogy Scaffold enforcement:
   - Step 1: Hook & Pain Point (1.5 min / ~200 words)
   - Step 2: Physical Intuition & Geometry (2.5 min / ~350 words)
   - Step 3: Formal Derivation & Mechanics (4.0 min / ~550 words)
   - Step 4: Engineering Takeaway & Boundary (1.5 min / ~200 words)
3. Dual-track Output Generation:
   - Track A: Presentation Deck (Clean 16:9 English Slides)
   - Track B: Bilingual Teleprompter Script (English Narration + Chinese Reference, 1150-1450 words)
4. Quality Gate Integration (CourseQAGate).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

try:
    from scripts.pipeline_state import PipelineStateDB, seed_standard_aerodynamics_symbols
    from scripts.qa_gate_validator import CourseQAGate, QAResult
except ImportError:
    from pipeline_state import PipelineStateDB, seed_standard_aerodynamics_symbols
    from qa_gate_validator import CourseQAGate, QAResult


FOUR_STEP_PEDAGOGY_PROMPT_TEMPLATE = """
You are the Lead Aerodynamics Professor & Technical Director. 
Generate a world-class, professional engineering lecture for episode {episode_id}: "{title}".

### Strict Specifications:
1. Total English spoken words MUST be strictly between 1,150 and 1,450 words (targeting 9.5 ± 0.5 minutes).
2. No fluff, no filler, no introductory chatter ("In this video...", "Welcome back...", "It is important to note..."). Start immediately with the physical conflict.
3. Every step in mathematical derivations MUST explicitly state its physical meaning.
4. Follow the 4-Step Pedagogy Scaffold with designated word counts:

---
### 4-Step Pedagogy Scaffold:
- [Hook & Pain Point] (~200 words): A concrete engineering breakdown, aerodynamic paradox, or counter-intuitive flow phenomenon.
- [Physical Intuition & Geometry] (~350 words): Geometric streamlines, surface topology, extreme Reynolds number limits (Re -> 0 or Re -> infinity). NO complex formulas here.
- [Formal Derivation & Mechanics] (~550 words): Step-by-step rigorous formulation of the governing equations. Never skip intermediate terms. Explain every physical tensor/term.
- [Engineering Takeaway & Boundary] (~200 words): Operational boundary conditions, wind tunnel / CFD calibration rules, and trade-offs in modern vehicle styling.

---
### Global Symbol Registry (Enforced LaTeX Symbols):
{symbol_context}

---
### Cumulative Ledger (Already Covered in Prior Lectures - DO NOT re-derive):
{covered_context}

---
### Forward Guard (Locked for Future Lessons - DO NOT spoil):
{forward_context}

---
### Output Format Requirements:
Provide TWO strictly aligned tracks:
1. [TRACK A: 16:9 English Slide Deck] (Markdown with '---' separating slides, clean, concise bullet points, LaTeX equations, and figure placeholders).
2. [TRACK B: Dual-language Teleprompter Script] (Full English spoken text verbatim, paired with paragraph-level Chinese translation for subtitles).
"""


class CourseCompiler:
    def __init__(self, db_path: Path):
        self.db = PipelineStateDB(db_path)
        # Auto-seed if symbol_registry is empty
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM symbol_registry")
        if cursor.fetchone()[0] == 0:
            seed_standard_aerodynamics_symbols(self.db)
        self.qa_gate = CourseQAGate()

    def build_prompt_for_episode(self, episode_info: Dict[str, Any]) -> str:
        episode_id = episode_info["episode"]
        title = episode_info["title"]

        # Fetch matching symbols from registry
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT * FROM symbol_registry")
        symbols = [dict(r) for r in cursor.fetchall()]
        symbol_lines = [
            f"- {s['canonical_en']} ({s['canonical_zh']}): {s['latex_repr']} [{s['standard_unit'] or 'dimensionless'}]"
            for s in symbols[:15]
        ]
        symbol_context = "\n".join(symbol_lines) if symbol_lines else "Standard aerodynamic notations apply."

        # Fetch covered ledger
        ledger = self.db.get_covered_ledger_up_to(180)
        if ledger:
            covered_lines = [
                f"- [{item['lesson_id']}] {item['concept_title']}: {item['key_conclusion_en']}"
                for item in ledger[-5:]
            ]
            covered_context = "\n".join(covered_lines)
        else:
            covered_context = "This is an introductory lecture or the first in this series."

        # Fetch forward guard
        cursor.execute("SELECT * FROM forward_guard WHERE planned_lesson_id > ?", (episode_id,))
        forwards = [dict(r) for r in cursor.fetchall()]
        forward_lines = [f"- {f['concept_id']}: reserved for {f['planned_lesson_id']}" for f in forwards[:5]]
        forward_context = "\n".join(forward_lines) if forward_lines else "None."

        return FOUR_STEP_PEDAGOGY_PROMPT_TEMPLATE.format(
            episode_id=episode_id,
            title=title,
            symbol_context=symbol_context,
            covered_context=covered_context,
            forward_context=forward_context,
        )

    def validate_generated_content(self, episode_id: str, script_text: str, slide_text: str) -> QAResult:
        return self.qa_gate.run_qa(episode_id, script_text, slide_text)


if __name__ == "__main__":
    compiler = CourseCompiler(Path("shared/state/aerodynamics_pipeline.db"))
    prompt = compiler.build_prompt_for_episode({
        "episode": "T1-01",
        "title": "Why Road Vehicles Are Fundamentally Bluff Body Problems",
    })
    print(f"Sample generated prompt preview:\n{prompt[:400]}...")
