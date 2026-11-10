from __future__ import annotations

import unittest

from course_control.alignment import _tokens


class CjkTokensTest(unittest.TestCase):
    def test_chinese_is_tokenized_by_character(self) -> None:
        self.assertEqual(_tokens("注意力，什麼是注意力"), list("注意力什么是注意力"))

    def test_english_tokenization_is_unchanged(self) -> None:
        self.assertEqual(_tokens("Attention is all you need."), ["attention", "is", "all", "you", "need"])

    def test_punctuation_is_dropped(self) -> None:
        self.assertEqual(_tokens("问、答、加权。"), list("问答加权"))


if __name__ == "__main__":
    unittest.main()
