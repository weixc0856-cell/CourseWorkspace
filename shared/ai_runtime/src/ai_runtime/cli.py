"""Command-line inspection for the shared AI runtime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .locks import FileLock, LockTimeout
from .service import ServerConfig, is_healthy, model_ids, port_in_use
from .tasks import TaskStore, schema


def _status(args: argparse.Namespace) -> int:
    server = ServerConfig(executable=args.executable, host=args.host, port=args.port)
    lock = FileLock(Path(args.lock), timeout_s=0)
    info = lock.read()
    payload = {
        "base_url": f"http://{args.host}:{args.port}",
        "healthy": is_healthy(server),
        "port_in_use": port_in_use(server),
        "models": model_ids(server),
        "lock": info.to_dict() if info else None,
        "lock_stale": lock.is_stale(info) if info else False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _unlock(args: argparse.Namespace) -> int:
    path = Path(args.lock)
    lock = FileLock(path, timeout_s=0)
    info = lock.read()
    if info is None:
        print("no lock held")
        return 0
    stale = lock.is_stale(info)
    if not stale and not args.force:
        print(f"lock is active (pid={info.pid} task={info.task_id}); use --force to override")
        return 2
    path.unlink(missing_ok=True)
    print("lock removed")
    return 0


def _tasks(args: argparse.Namespace) -> int:
    store = TaskStore(Path(args.root))
    records = store.list()
    if args.status:
        records = [record for record in records if record.status == args.status]
    print(json.dumps([record.as_dict() for record in records], ensure_ascii=False, indent=2))
    return 0


def _schema(_: argparse.Namespace) -> int:
    print(json.dumps(schema(), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status", help="show lock and local service state")
    status.add_argument("--lock", default="runtime/locks/llama-8080.lock")
    status.add_argument("--executable", default="")
    status.add_argument("--host", default="127.0.0.1")
    status.add_argument("--port", type=int, default=8080)
    status.set_defaults(func=_status)

    unlock = sub.add_parser("unlock", help="remove a stale lock")
    unlock.add_argument("--lock", default="runtime/locks/llama-8080.lock")
    unlock.add_argument("--force", action="store_true")
    unlock.set_defaults(func=_unlock)

    tasks = sub.add_parser("tasks", help="list model task records")
    tasks.add_argument("--root", default="runtime/tasks")
    tasks.add_argument("--status", choices=["pending", "running", "completed", "failed", "blocked", "needs_review", "skipped"])
    tasks.set_defaults(func=_tasks)

    schema_cmd = sub.add_parser("schema", help="print the task record JSON Schema")
    schema_cmd.set_defaults(func=_schema)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except LockTimeout as exc:
        print(str(exc), file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
