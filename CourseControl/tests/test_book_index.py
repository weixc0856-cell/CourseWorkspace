from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from course_control.production.book_index import (
    BookIndexError,
    check_cards,
    load_book_index,
    load_card,
    load_card_dir,
)

INDEX = {
    "concepts": [{"id": "1.1"}, {"id": "2.1.1"}],
    "claims": [{"id": "K-1"}],
    "figures": [{"id": "F-1.67"}],
    "sources": [{"chapter": "1", "page": 1}],
}


def card(episode="T1-01", **overrides):
    data = {
        "schema_version": 1,
        "episode": episode,
        "title": "Why",
        "core_question": "Why?",
        "target_seconds": 600,
        "concepts": ["1.1"],
        "claims": ["K-1"],
        "figures": ["F-1.67"],
        "prerequisites": [],
        "cut_list": ["history"],
        "status": "card",
    }
    data.update(overrides)
    return data


class BookIndexTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, data, episode="T1-01", name="card.yaml"):
        import yaml

        path = self.root / "cards" / episode / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return path

    def test_valid_card_passes(self):
        self._write(card())
        problems = check_cards(INDEX, load_card_dir(self.root / "cards"))
        self.assertEqual(problems, [])

    def test_unknown_concept_fails(self):
        self._write(card(concepts=["9.9"]))
        problems = check_cards(INDEX, load_card_dir(self.root / "cards"))
        self.assertTrue(any("unknown concept 9.9" in item for item in problems))

    def test_unknown_claim_fails(self):
        self._write(card(claims=["K-404"]))
        problems = check_cards(INDEX, load_card_dir(self.root / "cards"))
        self.assertTrue(any("unknown claim K-404" in item for item in problems))

    def test_unknown_figure_fails(self):
        self._write(card(figures=["F-9.9"]))
        problems = check_cards(INDEX, load_card_dir(self.root / "cards"))
        self.assertTrue(any("unknown figure F-9.9" in item for item in problems))

    def test_duplicate_episode_fails(self):
        self._write(card(), episode="T1-01")
        self._write(card(), episode="T1-01", name="card-copy.yaml")
        cards = [load_card(self.root / "cards" / "T1-01" / "card.yaml"), load_card(self.root / "cards" / "T1-01" / "card.yaml")]
        problems = check_cards(INDEX, cards)
        self.assertTrue(any("duplicate episode" in item for item in problems))

    def test_card_needs_cut_list(self):
        data = card()
        data["cut_list"] = []
        with self.assertRaises(BookIndexError):
            load_card(self._write(data))

    def test_target_seconds_must_fit_the_window(self):
        with self.assertRaises(BookIndexError):
            load_card(self._write(card(target_seconds=300)))

    def test_index_needs_required_lists(self):
        path = self.root / "index.json"
        path.write_text(json.dumps({"concepts": []}), encoding="utf-8")
        with self.assertRaises(BookIndexError):
            load_book_index(path)


if __name__ == "__main__":
    unittest.main()
