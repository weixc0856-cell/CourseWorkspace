"""Token audit for Claude Code session transcripts (协作协议 §12).

Usage: python scripts/analyze_session_tokens.py [--json] <session.jsonl> [<more.jsonl> ...]

Read-only. Prints per-session API call counts, context growth, cache/input/output
totals, a cost-weighted estimate, and the largest tool-result / re-read offenders.
Transcripts live under ~/.claude/projects/<project-slug>/*.jsonl.

``--json`` emits one structured object per session (key ``cost_weighted`` is the
cost-weighted estimate the release-check token-bill gate reads).  The bill is
saved as ``build/_logs/token-bill-<lesson>.json``; an over-baseline run needs a
``token-bill-<lesson>-note.md`` explanation beside it (see release/check.py).
"""
import json
import sys
from collections import defaultdict


def collect(path):
    calls = {}  # requestId -> usage (dedup split content blocks)
    tool_uses = {}  # id -> (name, target)
    cmd_by_id = {}  # id -> full command (Bash/PowerShell retry detection)
    result_chars = defaultdict(int)
    file_chars = defaultdict(int)
    file_reads = defaultdict(int)
    payload_chars = defaultdict(int)
    tool_errors = defaultdict(int)
    error_signatures = defaultdict(int)
    command_counts = defaultdict(int)
    large_writes = []
    images = 0
    sidechain_calls = 0
    compact_events = 0
    models = defaultdict(int)
    contexts = []
    n_lines = 0

    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            n_lines += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("isCompactSummary") or obj.get("subtype") == "compact_boundary":
                compact_events += 1
            typ = obj.get("type")
            msg = obj.get("message") or {}
            content = msg.get("content")
            if typ == "assistant":
                usage = msg.get("usage") or {}
                rid = obj.get("requestId") or obj.get("uuid")
                if usage and rid not in calls:
                    calls[rid] = usage
                    models[msg.get("model", "?")] += 1
                    if obj.get("isSidechain"):
                        sidechain_calls += 1
                    contexts.append(
                        usage.get("input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                    )
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        kind = block.get("type")
                        if kind == "tool_use":
                            inp = block.get("input") or {}
                            target = (inp.get("file_path") or inp.get("path")
                                      or inp.get("pattern")
                                      or str(inp.get("command", ""))[:60])
                            tool_uses[block.get("id")] = (block.get("name", "?"), str(target))
                            payload_chars["tool_use_input"] += len(
                                json.dumps(inp, ensure_ascii=False))
                            name = block.get("name", "?")
                            if name in ("Bash", "PowerShell") and inp.get("command"):
                                cmd_by_id[block.get("id")] = inp["command"]
                                command_counts[inp["command"]] += 1
                            if name in ("Write", "Edit"):
                                body = inp.get("content") or inp.get("new_string") or ""
                                if len(body) > 8000:
                                    large_writes.append(
                                        {"target": str(target), "chars": len(body)})
                        elif kind == "text":
                            payload_chars["assistant_text"] += len(block.get("text", ""))
                        elif kind == "thinking":
                            payload_chars["thinking"] += len(block.get("thinking", ""))
            elif typ == "user":
                if isinstance(content, str):
                    payload_chars["user_text"] += len(content)
                    continue
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "text":
                        payload_chars["user_text"] += len(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        name, target = tool_uses.get(block.get("tool_use_id"), ("?", "?"))
                        body = block.get("content")
                        size = 0
                        text_parts = []
                        if isinstance(body, str):
                            size = len(body)
                            text_parts.append(body)
                        elif isinstance(body, list):
                            for part in body:
                                if not isinstance(part, dict):
                                    continue
                                if part.get("type") == "text":
                                    size += len(part.get("text", ""))
                                    text_parts.append(part.get("text", ""))
                                elif part.get("type") == "image":
                                    images += 1
                                    size += 4000  # placeholder; images counted separately
                        result_chars[name] += size
                        if block.get("is_error"):
                            tool_errors[name] += 1
                            sig = " ".join(" ".join(text_parts).split())[:100]
                            if sig:
                                error_signatures[sig] += 1
                        if name in ("Read", "Edit", "Write"):
                            file_chars[target] += size
                            if name == "Read":
                                file_reads[target] += 1

    tot = defaultdict(int)
    for usage in calls.values():
        for key in ("input_tokens", "cache_creation_input_tokens",
                    "cache_read_input_tokens", "output_tokens"):
            tot[key] += usage.get(key, 0)
    contexts.sort()
    n = len(contexts)
    weighted = (tot["input_tokens"] + tot["cache_creation_input_tokens"] * 1.25
                + tot["cache_read_input_tokens"] * 0.1 + tot["output_tokens"] * 5)
    context = (
        {"first": contexts[0], "median": contexts[n // 2],
         "p90": contexts[int(n * 0.9)], "max": contexts[-1]}
        if n else {"first": 0, "median": 0, "p90": 0, "max": 0}
    )
    reread = [
        {"target": target, "reads": cnt, "chars": file_chars[target]}
        for target, cnt in sorted(file_reads.items(), key=lambda x: -file_chars[x[0]])[:10]
    ]
    repeated = [
        {"command": cmd[:100], "times": cnt}
        for cmd, cnt in sorted(command_counts.items(), key=lambda x: -x[1])
        if cnt >= 3
    ][:8]
    pitfalls = {
        "tool_errors": dict(sorted(tool_errors.items(), key=lambda x: -x[1])),
        "top_error_signatures": [
            {"signature": sig, "times": cnt}
            for sig, cnt in sorted(error_signatures.items(), key=lambda x: -x[1])[:6]
        ],
        "repeated_commands": repeated,
        "large_write_payloads": {
            "count": len(large_writes),
            "chars": sum(w["chars"] for w in large_writes),
            "targets": sorted({w["target"] for w in large_writes})[:10],
        },
    }
    return {
        "path": str(path),
        "lines": n_lines,
        "api_calls": n,
        "sidechain_calls": sidechain_calls,
        "compact_events": compact_events,
        "images_read": images,
        "models": dict(models),
        "input_tokens": tot["input_tokens"],
        "cache_creation_input_tokens": tot["cache_creation_input_tokens"],
        "cache_read_input_tokens": tot["cache_read_input_tokens"],
        "output_tokens": tot["output_tokens"],
        "cost_weighted": weighted,
        "context": context,
        "payload_chars": dict(sorted(payload_chars.items(), key=lambda x: -x[1])),
        "tool_result_chars": dict(sorted(result_chars.items(), key=lambda x: -x[1])[:8]),
        "reread_files": reread,
        "pitfalls": pitfalls,
    }


def render_text(s):
    lines = [
        f"\n=== {s['path']}",
        f"lines={s['lines']} api_calls={s['api_calls']} sidechain_calls={s['sidechain_calls']} "
        f"compact_events={s['compact_events']} images_read={s['images_read']}",
        f"models={s['models']}",
        f"input={s['input_tokens']:,} cache_write={s['cache_creation_input_tokens']:,} "
        f"cache_read={s['cache_read_input_tokens']:,} output={s['output_tokens']:,}",
        f"cost-weighted units (in=1, cw=1.25, cr=0.1, out=5): {s['cost_weighted']:,.0f}",
    ]
    c = s["context"]
    if s["api_calls"]:
        lines.append(
            f"context/call: first={c['first']:,} median={c['median']:,} "
            f"p90={c['p90']:,} max={c['max']:,}"
        )
    lines.append("context payload (chars, ~3 chars/token):")
    for key, size in s["payload_chars"].items():
        lines.append(f"  {key:<18} {size:>12,}")
    lines.append("tool result volume (chars):")
    for name, size in s["tool_result_chars"].items():
        lines.append(f"  {name:<22} {size:>12,}")
    lines.append("most re-read files (Read count, total chars):")
    for item in s["reread_files"]:
        lines.append(f"  {item['reads']:>3}x {item['chars']:>10,}  {item['target']}")
    p = s["pitfalls"]
    lines.append(f"pitfalls: tool_errors={p['tool_errors']}")
    for item in p["top_error_signatures"]:
        lines.append(f"  {item['times']:>3}x  {item['signature']}")
    for item in p["repeated_commands"]:
        lines.append(f"  {item['times']:>3}x  {item['command']}")
    lw = p["large_write_payloads"]
    lines.append(
        f"large Write/Edit payloads (>8K chars): {lw['count']} calls, {lw['chars']:,} chars"
    )
    for target in lw["targets"]:
        lines.append(f"       {target}")
    return "\n".join(lines)


def summarize(path):
    print(render_text(collect(path)))


def main(argv):
    as_json = False
    paths = []
    for arg in argv:
        if arg == "--json":
            as_json = True
        else:
            paths.append(arg)
    if not paths:
        print(__doc__)
        return 2
    for p in paths:
        stats = collect(p)
        if as_json:
            print(json.dumps(stats, ensure_ascii=False))
        else:
            print(render_text(stats))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))