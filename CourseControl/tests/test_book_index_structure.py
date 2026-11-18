"""Structural checks for the book index and the episode cards.

The old check only asked "does this id exist?".  These tests lock the rest:
the card count matches the course map, a card's section matches its figures'
parent section, a cross-section figure must declare borrow_from, true caption
ids are unique, and a multi-asset figure keeps all its panels.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from course_control.production.book_index import (
    EpisodeCard,
    check_cards,
    load_card,
    load_course_map,
)


def _index(schema: int = 2) -> dict:
    data = {
        "schema_version": schema,
        "concepts": [{"id": "1.1"}, {"id": "1.2"}],
        "claims": [],
        "figures": [
            {"id": "F-1.1", "join_status": "caption", "assets": ["a.png"], "parent_section": "1.1"},
            {"id": "F-1.2", "join_status": "caption", "assets": ["b.png"], "parent_section": "1.2"},
            {
                "id": "F-1.9",
                "join_status": "multi_asset",
                "assets": ["c.png", "d.png"],
                "parent_section": "1.2",
            },
        ],
        "unassigned_pictures": [],
        "sources": [],
    }
    if schema == 1:
        for figure in data["figures"]:
            figure.pop("join_status", None)
            figure.pop("assets", None)
            figure.pop("parent_section", None)
        data.pop("unassigned_pictures", None)
    return data


def _card(
    episode: str = "T1-01",
    section: str | None = "1.1",
    figures: tuple[str, ...] = ("F-1.1",),
    borrow_from: tuple[dict, ...] = (),
) -> EpisodeCard:
    return EpisodeCard(
        path=Path(episode) / "card.yaml",
        episode=episode,
        title="t",
        core_question="q",
        target_seconds=720,
        concepts=["1.1"],
        claims=[],
        figures=list(figures),
        prerequisites=[],
        cut_list=["x"],
        section=section,
        borrow_from=list(borrow_from),
    )


def _map(*rows: tuple[str, str, str, int]) -> list[dict]:
    return [
        {"episode": episode, "title": title, "section": section, "minutes": minutes}
        for episode, title, section, minutes in rows
    ]


class BookIndexStructureTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_clean_structure_passes(self) -> None:
        problems = check_cards(
            _index(), [_card()], _map(("T1-01", "t", "1.1", 12))
        )
        self.assertEqual([], problems)

    def test_map_may_detail_an_episode_before_its_card(self) -> None:
        problems = check_cards(
            _index(),
            [_card()],
            _map(("T1-01", "t", "1.1", 12), ("T1-02", "t", "1.2", 10)),
        )
        self.assertEqual([], problems)

    def test_card_outside_the_map_fails(self) -> None:
        problems = check_cards(
            _index(),
            [_card(episode="T2-01")],
            _map(("T1-01", "t", "1.1", 12)),
        )
        self.assertTrue(any("is not in the map" in item for item in problems), problems)

    def test_card_section_must_match_map(self) -> None:
        problems = check_cards(
            _index(), [_card(section="1.1")], _map(("T1-01", "t", "1.2", 12))
        )
        self.assertTrue(any("card section" in item for item in problems), problems)

    def test_cross_section_figure_needs_borrow(self) -> None:
        problems = check_cards(
            _index(),
            [_card(figures=("F-1.2",))],
            _map(("T1-01", "t", "1.1", 12)),
        )
        self.assertTrue(any("belongs to 1.2" in item for item in problems), problems)

    def test_borrow_from_allows_cross_section(self) -> None:
        problems = check_cards(
            _index(),
            [_card(figures=("F-1.2",), borrow_from=({"section": "1.2", "reason": "teaser"},))],
            _map(("T1-01", "t", "1.1", 12)),
        )
        self.assertEqual([], problems)

    def test_duplicate_true_caption_fails(self) -> None:
        index = _index()
        index["figures"].append(dict(index["figures"][0]))
        problems = check_cards(index, [_card()], _map(("T1-01", "t", "1.1", 12)))
        self.assertTrue(any("duplicate true caption" in item for item in problems), problems)

    def test_multi_asset_needs_two_assets(self) -> None:
        index = _index()
        index["figures"][2]["assets"] = ["c.png"]
        problems = check_cards(index, [_card()], _map(("T1-01", "t", "1.1", 12)))
        self.assertTrue(any("at least two assets" in item for item in problems), problems)

    def test_missing_unassigned_list_fails(self) -> None:
        index = _index()
        index.pop("unassigned_pictures")
        problems = check_cards(index, [_card()], _map(("T1-01", "t", "1.1", 12)))
        self.assertTrue(any("unassigned_pictures" in item for item in problems), problems)

    def test_schema_one_skips_structural_checks(self) -> None:
        problems = check_cards(
            _index(schema=1), [_card(section=None)], _map(("T1-01", "t", "1.1", 12))
        )
        self.assertEqual([], problems)

    def test_course_map_parser(self) -> None:
        path = self.root / "COURSE_MAP.md"
        path.write_text(
            "| 集 | 集名 | 原书小节 | 页码 | 时长 |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| T1-01 | 汽车为什么需要空气动力学 | 1.1 Scope | 22–27 | 12 |\n"
            "| T1-02 | 速度第一次撞上空气 | 1.2 Historical Development | 28–46 | 15 |\n"
            "| | | | **74 页** | **118** |\n",
            encoding="utf-8",
        )
        rows = load_course_map(path)
        self.assertEqual([row["episode"] for row in rows], ["T1-01", "T1-02"])
        self.assertEqual(rows[0]["section"], "1.1")
        self.assertEqual(rows[1]["minutes"], 15)

    def test_card_reads_section_and_borrow_from(self) -> None:
        path = self.root / "card.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 1,
                    "episode": "T1-01",
                    "title": "t",
                    "core_question": "q",
                    "target_seconds": 600,
                    "section": "1.1",
                    "concepts": ["1.1"],
                    "claims": [],
                    "figures": ["F-1.1"],
                    "borrow_from": [{"section": "1.2", "reason": "teaser"}],
                    "prerequisites": [],
                    "cut_list": ["x"],
                    "status": "card",
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        card = load_card(path)
        self.assertEqual(card.section, "1.1")
        self.assertEqual(card.borrow_from[0]["section"], "1.2")


if __name__ == "__main__":
    unittest.main()
