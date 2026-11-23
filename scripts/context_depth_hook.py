"""PostToolUse hook: nudge the agent to compact when the session grows deep.

Reads the hook JSON on stdin, stats the session transcript, and emits a §12
reminder via additionalContext once per growth step (1.5 MB ~ 100K context).
Never blocks: any problem exits 0 silently.
"""
import json
import os
import sys
import tempfile

STEP_BYTES = 1_500_000


def main():
    try:
        payload = json.load(sys.stdin)
        path = payload.get("transcript_path")
        session = payload.get("session_id", "unknown")
        if not path or not os.path.isfile(path):
            return
        size = os.path.getsize(path)
        level = size // STEP_BYTES
        if level < 1:
            return
        marker = os.path.join(tempfile.gettempdir(), f"claude-depth-nudge-{session}.json")
        last = 0
        try:
            with open(marker, encoding="utf-8") as fh:
                last = json.load(fh).get("level", 0)
        except (OSError, ValueError):
            pass
        if level <= last:
            return
        with open(marker, "w", encoding="utf-8") as fh:
            json.dump({"level": level}, fh)
        # ensure_ascii: Windows piped stdout may be GBK; \uXXXX survives any codepage.
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"§12 上下文纪律自动提醒：本会话 transcript 已达 {size // 1000} KB"
                    f"（约 {level * 100}K 上下文）。阶段结束请 /compact 或开新会话并先读交接文件；"
                    "大产物走生成器落盘、命令输出截流到 build/_logs/、审阅派子代理。"
                    "此提醒自动触发，不需 owner 提示；硬门仍只卡交付质量。"
                ),
            }
        }))
    except Exception:
        return


if __name__ == "__main__":
    main()