"""Poll ComfyUI /queue until both queue_running and queue_pending are empty.

Exit 0 = GPU free; exit 2 = timed out still busy. Connection refused counts as
free after 3 consecutive failures (ComfyUI stopped).
"""
import json
import sys
import time
import urllib.request

URL = "http://127.0.0.1:8188/queue"
INTERVAL = 30
MAX_MINUTES = float(sys.argv[1]) if len(sys.argv) > 1 else 45.0


def log(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def main():
    deadline = time.time() + MAX_MINUTES * 60
    conn_fails = 0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(URL, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            conn_fails = 0
            running = len(data.get("queue_running", []))
            pending = len(data.get("queue_pending", []))
            log(f"queue_running={running} queue_pending={pending}")
            if running == 0 and pending == 0:
                log("GPU_FREE")
                return 0
        except Exception as exc:
            conn_fails += 1
            log(f"conn_fail={conn_fails} ({type(exc).__name__})")
            if conn_fails >= 3:
                log("GPU_FREE (ComfyUI unreachable)")
                return 0
        time.sleep(INTERVAL)
    log("TIMEOUT_STILL_BUSY")
    return 2


if __name__ == "__main__":
    sys.exit(main())
