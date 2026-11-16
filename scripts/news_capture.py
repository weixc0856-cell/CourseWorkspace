"""Capture news source pages into the content root and record provenance.

Nothing is written into the repository: pages land in
`<content_root>/runtime/news-capture/<slug>/`, each with a sha256, a capture
timestamp and the original URL, so the ledger can prove where a frame came from.

Browser capture is delegated to Node because playwright is only installed as a
Node module here. Python orchestrates, hashes and records.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "CourseControl" / "src"))
from course_control.platform.workspace_layout import content_root  # noqa: E402

SHOT_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const [url, out, width, height] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({
    viewport: { width: Number(width), height: Number(height) },
    deviceScaleFactor: 1.5,
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      + '(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36',
  });
  try {
    const r = await p.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await p.waitForTimeout(2000);
    // dismiss consent banners so they do not cover the document
    for (const label of ['Reject Optional', 'Accept All', 'Accept', 'I Agree']) {
      try {
        const btn = p.locator(`button:has-text("${label}")`).first();
        if (await btn.isVisible({ timeout: 700 })) {
          await btn.click({ timeout: 2500 });
          await p.waitForTimeout(1000);
          break;
        }
      } catch (e) { /* banner absent or not clickable */ }
    }
    // last resort: paint over consent overlays so the document is legible
    try {
      await p.addStyleTag({ content:
        '[class*="cookie"],[id*="cookie"],[class*="consent"],[id*="consent"],' +
        '[class*="gdpr"],[id*="gdpr"],[class*="privacy"][class*="banner"]' +
        '{display:none !important}' });
    } catch (e) { /* nothing to hide */ }
    await p.waitForTimeout(1200);
    await p.screenshot({ path: out, fullPage: false });
    console.log(JSON.stringify({ status: r ? r.status() : 0, title: await p.title() }));
  } catch (e) {
    console.log(JSON.stringify({ status: 0, error: String(e.message).split('\n')[0] }));
  }
  await b.close();
})();
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_playwright_engine(workspace: Path) -> Path:
    """Return a node_modules directory that has playwright installed."""
    for candidate in sorted(workspace.glob("**/node_modules/playwright")):
        if candidate.is_dir() and "CourseWorkspace" not in str(candidate.parent.parent.parent):
            return candidate.parent
    for candidate in sorted((content_root(workspace)).glob("engines/**/node_modules/playwright")):
        if candidate.is_dir():
            return candidate.parent
    raise SystemExit("no node_modules with playwright found; pass --node-modules")


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")


def _download_pdf(url: str, out_pdf: Path) -> dict:
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            out_pdf.write_bytes(response.read())
    except Exception as exc:  # noqa: BLE001
        return {"status": 0, "error": str(exc)[:200]}
    if status != 200:
        return {"status": status, "error": "download failed"}
    return {"status": status, "title": out_pdf.name}


def _pdf_first_page(out_pdf: Path, out_png: Path) -> bool:
    prefix = out_png.with_suffix("")
    proc = subprocess.run(
        ["pdftoppm", "-f", "1", "-l", "1", "-png", "-r", "110", str(out_pdf), str(prefix)],
        capture_output=True, text=True,
    )
    produced = sorted(out_png.parent.glob(prefix.name + "-*.png"))
    if not produced:
        return False
    produced[0].replace(out_png)
    return True


def _capture(url: str, out_png: Path, node_modules: Path, size: tuple[int, int]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "shot.cjs"
        script.write_text(SHOT_JS, encoding="utf-8")
        env = dict(__import__("os").environ)
        env["NODE_PATH"] = str(node_modules)
        proc = subprocess.run(
            ["node", str(script), url, str(out_png), str(size[0]), str(size[1])],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        )
        line = (proc.stdout or "").strip().splitlines()
        if not line:
            return {"status": 0, "error": (proc.stderr or "no output").strip()[:200]}
        try:
            return json.loads(line[-1])
        except json.JSONDecodeError:
            return {"status": 0, "error": line[-1][:200]}


def main() -> int:
    parser = argparse.ArgumentParser(description="capture news source pages into the content root")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--slug", required=True)
    parser.add_argument("--size", default="1920x1080")
    parser.add_argument("--only", default="", help="comma separated asset ids")
    parser.add_argument("--node-modules", type=Path, default=None)
    parser.add_argument("--update-ledger", action="store_true")
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    root = content_root(workspace)
    lesson_dir = root / "lessons" / args.slug / "authoring"
    ledger_path = lesson_dir / "ledger.yaml"
    if not ledger_path.is_file():
        raise SystemExit(f"ledger not found: {ledger_path}")

    out_dir = root / "runtime" / "news-capture" / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    node_modules = args.node_modules or _find_playwright_engine(workspace)
    width, height = (int(v) for v in args.size.lower().split("x"))
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    ledger = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    report = []
    for record in ledger.get("records", []):
        asset_id = record.get("asset_id")
        url = record.get("source_url")
        if only and asset_id not in only:
            continue
        if not url:
            report.append({"asset_id": asset_id, "status": "skipped", "error": "no source_url"})
            continue
        out_png = out_dir / f"{asset_id}.png"
        if url.lower().split("?")[0].endswith(".pdf"):
            out_pdf = out_dir / f"{asset_id}.pdf"
            result = _download_pdf(url, out_pdf)
            if result.get("status") == 200 and not _pdf_first_page(out_pdf, out_png):
                result = {"status": 0, "error": "pdftoppm failed"}
        else:
            result = _capture(url, out_png, node_modules, (width, height))
        captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
        ok = result.get("status") == 200 and out_png.is_file()
        entry = {
            "asset_id": asset_id,
            "url": url,
            "status": result.get("status"),
            "title": result.get("title"),
            "captured_at": captured_at,
            "path": str(out_png).replace(chr(92), "/") if ok else None,
            "sha256": _sha256(out_png) if ok else None,
            "error": result.get("error"),
        }
        report.append(entry)
        if ok and args.update_ledger:
            record["path"] = str(out_png).replace(chr(92), "/")
            record["captured_at"] = captured_at
        marker = "ok " if ok else "ERR"
        print(f"  [{marker}] {asset_id} {result.get('status')} {url}")

    # merge with earlier runs so --only does not erase the other records
    merged = {}
    if (out_dir / "capture.json").is_file():
        try:
            for item in json.loads((out_dir / "capture.json").read_text(encoding="utf-8"))["captures"]:
                merged[item["asset_id"]] = item
        except (json.JSONDecodeError, KeyError):
            pass
    for item in report:
        merged[item["asset_id"]] = item
    (out_dir / "capture.json").write_text(
        json.dumps({"slug": args.slug, "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "captures": [merged[k] for k in sorted(merged)]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.update_ledger:
        ledger_path.write_text(yaml.safe_dump(ledger, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"ledger updated: {ledger_path}")

    captured = sum(1 for r in report if r.get("sha256"))
    print(f"captured {captured} of {len(report)} -> {out_dir}")
    return 0 if captured else 1


if __name__ == "__main__":
    raise SystemExit(main())
