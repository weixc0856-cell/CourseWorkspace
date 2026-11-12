"""Source ingestion for the R1 authoring pipeline.

V1 supports web URLs, local Markdown and plain text. It uses only the standard
library: ``urllib`` for fetching (proxy-disabled, like the model probes) and
``HTMLParser`` for a conservative readability pass. No paywall or JavaScript
bypass is attempted; empty extraction is an explicit failure.
"""

from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import yaml

from course_control.authoring.models import SourceEntry, SourcesFile

MAX_BYTES = 5 * 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class IngestError(RuntimeError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class _Extractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "noscript", "svg", "form"}
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "td", "th"}
    HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.blocks: list[tuple[str, str]] = []
        self._skip_depth = 0
        self._capture_title = False
        self._title_buf: list[str] = []
        self._block_tag: str | None = None
        self._buf: list[str] = []
        self._in_article = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in self.SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in ("article", "main"):
            self._in_article += 1
            return
        if tag == "title":
            self._capture_title = True
            return
        if tag == "br":
            self._buf.append("\n")
            return
        if tag in self.BLOCK and self._block_tag is None:
            self._flush()
            self._block_tag = tag
            return
        if tag in self.BLOCK:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag in ("article", "main"):
            self._in_article = max(0, self._in_article - 1)
            return
        if tag == "title":
            self._capture_title = False
            self.title = " ".join("".join(self._title_buf).split())
            return
        if tag in self.BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._title_buf.append(data)
            return
        if self._skip_depth:
            return
        if self._block_tag is not None:
            self._buf.append(data)
        elif data.strip():
            self._buf.append(data)

    def _flush(self) -> None:
        text = re.sub(r"[ \t\r\f\v]+", " ", "".join(self._buf)).strip()
        text = re.sub(r"\n{2,}", "\n", text)
        if text:
            self.blocks.append((self._block_tag or "p", text))
        self._buf = []
        self._block_tag = None


def html_to_markdown(html: str) -> tuple[str, str]:
    parser = _Extractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"HTML parse failed: {exc}") from exc
    lines: list[str] = []
    for tag, text in parser.blocks:
        if tag in parser.HEADINGS:
            lines.append("#" * parser.HEADINGS[tag] + " " + text)
        elif tag == "li":
            lines.append("- " + text)
        else:
            lines.append(text)
    markdown = "\n\n".join(line for line in lines if line.strip()).strip()
    return parser.title, markdown


def fetch_url(url: str, timeout: float = 30.0) -> tuple[int, str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise IngestError(f"unsupported URL scheme: {parsed.scheme}")
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            "Accept-Language": "en,zh-CN;q=0.8",
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            data = response.read(MAX_BYTES + 1)
            content_type = response.headers.get("Content-Type", "")
            charset = response.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        raise IngestError(f"HTTP {exc.code} for {url}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise IngestError(f"fetch failed for {url}: {exc}") from exc
    if len(data) > MAX_BYTES:
        raise IngestError(f"page exceeds {MAX_BYTES} bytes: {url}")
    if "html" in content_type.lower() or "xml" in content_type.lower() or not content_type:
        text = data.decode(charset, errors="replace")
        return status, text, "html"
    if "text/" in content_type.lower() or "json" in content_type.lower():
        return status, data.decode(charset, errors="replace"), "text"
    raise IngestError(f"unsupported content type {content_type!r} for {url}")


def _next_id(existing: SourcesFile) -> str:
    used = {source.id for source in existing.sources}
    for number in range(1, 1000):
        candidate = f"S{number}"
        if candidate not in used:
            return candidate
    raise IngestError("source id space exhausted")


def load_sources(path: Path) -> SourcesFile:
    if not path.is_file():
        return SourcesFile(lesson=path.parent.parent.name)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SourcesFile.model_validate(data)


def ingest(
    workspace: Path,
    lesson_dir: Path,
    source: str,
    *,
    kind: str = "auto",
    source_id: str | None = None,
) -> SourceEntry:
    lesson_dir = lesson_dir.resolve()
    workspace = workspace.resolve()
    slug = lesson_dir.name
    authoring = lesson_dir / "authoring"
    sources_dir = authoring / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = authoring / "sources.yaml"
    manifest = load_sources(manifest_path)
    manifest = SourcesFile(lesson=slug, sources=manifest.sources)

    source_id = source_id or _next_id(manifest)
    if any(entry.id == source_id for entry in manifest.sources):
        raise IngestError(f"source id already exists: {source_id}")

    if kind == "auto":
        if source.startswith(("http://", "https://")):
            kind = "url"
        elif Path(source).suffix.lower() in (".md", ".markdown"):
            kind = "markdown"
        else:
            kind = "text"

    title = ""
    http_status: int | None = None
    extractor = "stdlib"
    if kind == "url":
        http_status, payload, payload_kind = fetch_url(source)
        if payload_kind == "html":
            title, body = html_to_markdown(payload)
        else:
            body = payload.strip()
            if body and not body.lstrip().startswith("#"):
                body = "# Source\n\n" + body
        origin = source
    elif kind in ("markdown", "text"):
        path = Path(source)
        if not path.is_absolute():
            path = (workspace / path).resolve()
        if not path.is_file():
            raise IngestError(f"source file not found: {path}")
        body = path.read_text(encoding="utf-8", errors="replace").strip()
        if not body:
            raise IngestError(f"source file is empty: {path}")
        if body.lstrip().startswith("#"):
            title = body.lstrip().splitlines()[0].lstrip("#").strip()
        else:
            title = path.stem
            if kind == "markdown":
                body = f"# {title}\n\n{body}"
        origin = path.relative_to(workspace).as_posix() if path.is_relative_to(workspace) else str(path)
    else:
        raise IngestError(f"unsupported source kind: {kind}")

    if not body.strip():
        raise IngestError("no readable text extracted from source")

    content = body.rstrip() + "\n"
    local_path = sources_dir / f"{source_id}.md"
    local_path.write_text(content, encoding="utf-8")
    entry = SourceEntry(
        id=source_id,
        kind=kind,
        origin=origin,
        local_path=f"authoring/sources/{source_id}.md",
        sha256=sha256_text(content),
        title=title or source_id,
        fetched_at=_now(),
        http_status=http_status,
        extractor=extractor,
    )
    manifest.sources.append(entry)
    manifest_path.write_text(
        yaml.safe_dump(
            manifest.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return entry
