"""SessionStart hook: inject the visual/animation hard-rules digest.

Fires on startup/resume/compact so production sessions always carry the visual
contract without having to remember to read the specs. Reads the digest file at
runtime (single source: CourseControl/prompts/visual-hard-rules.md). Never blocks.
"""
import json
import os
import sys

DIGEST = os.path.join("CourseControl", "prompts", "visual-hard-rules.md")


def main():
    try:
        with open(DIGEST, encoding="utf-8") as fh:
            text = fh.read().strip()
        if not text:
            return
        # ensure_ascii: Windows piped stdout may be GBK; \uXXXX survives any codepage.
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": (
                    "视觉与动画硬规则（每次会话自动注入，来源 docs/ 视觉规范，必须执行）：\n"
                    + text
                ),
            }
        }))
    except Exception:
        return


if __name__ == "__main__":
    main()