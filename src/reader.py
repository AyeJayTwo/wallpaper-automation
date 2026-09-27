"""Readwise Reader integration — list and download saved documents as EPUBs."""
from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence
from xml.sax.saxutils import escape

# Load token from .env (same pattern as readwise.py / todoist.py)
def _load_env() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env()

READWISE_TOKEN = os.environ.get("READWISE_TOKEN", "")
READER_BASE_URL = "https://readwise.io/api/v3"
DEFAULT_LOCATIONS = ("new",)
# Categories that make sense as readable files on CrossPoint (.epub/.txt/.pdf)
DOWNLOADABLE_CATEGORIES = frozenset({
    "article",
    "email",
    "rss",
    "pdf",
    "epub",
})
# Skip highlights/notes which also appear in the document list
SKIP_IF_PARENT = True

log = logging.getLogger(__name__)


@dataclass
class ReaderDocument:
    """A top-level document from the Reader library."""
    id: str
    title: str
    author: str
    category: str
    location: str
    source_url: str
    saved_at: str
    updated_at: str
    word_count: int
    html_content: str = ""
    raw_source_url: str = ""
    summary: str = ""
    site_name: str = ""

    @classmethod
    def from_api(cls, data: dict) -> "ReaderDocument":
        title = (data.get("title") or "Untitled").strip() or "Untitled"
        author = (data.get("author") or data.get("site_name") or "Unknown").strip()
        return cls(
            id=str(data.get("id", "")),
            title=title,
            author=author,
            category=str(data.get("category") or "article"),
            location=str(data.get("location") or ""),
            source_url=str(data.get("source_url") or data.get("url") or ""),
            saved_at=str(data.get("saved_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            word_count=int(data.get("word_count") or 0),
            html_content=str(data.get("html_content") or data.get("content") or ""),
            raw_source_url=str(data.get("raw_source_url") or ""),
            summary=str(data.get("summary") or ""),
            site_name=str(data.get("site_name") or ""),
        )


def _api_get(params: dict) -> dict:
    """GET https://readwise.io/api/v3/list/ with auth."""
    if not READWISE_TOKEN:
        raise ValueError("READWISE_TOKEN not set in .env file")

    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{READER_BASE_URL}/list/?{query}" if query else f"{READER_BASE_URL}/list/"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Token {READWISE_TOKEN}")
    req.add_header("User-Agent", "wallpaper-automation-reader/1.0")

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 429:
            retry_after = int(e.headers.get("Retry-After", "5"))
            raise RuntimeError(f"Reader API rate limited; retry after {retry_after}s") from e
        raise RuntimeError(f"Reader API error: {e.code} - {body}") from e


def list_documents(
    *,
    location: Optional[str] = None,
    category: Optional[str] = None,
    updated_after: Optional[str] = None,
    with_html: bool = False,
    with_raw_source: bool = False,
    limit: int = 100,
    max_pages: int = 20,
) -> List[dict]:
    """
    Paginate through Reader Document LIST.

    Rate limit is 20/min — callers should keep page counts modest.
    """
    results: List[dict] = []
    next_page_cursor: Optional[str] = None
    pages = 0

    while pages < max_pages:
        params: dict = {"limit": min(max(limit, 1), 100)}
        if location:
            params["location"] = location
        if category:
            params["category"] = category
        if updated_after:
            params["updatedAfter"] = updated_after
        if with_html:
            params["withHtmlContent"] = "true"
        if with_raw_source:
            params["withRawSourceUrl"] = "true"
        if next_page_cursor:
            params["pageCursor"] = next_page_cursor

        data = _api_get(params)
        batch = data.get("results") or []
        results.extend(batch)
        pages += 1
        next_page_cursor = data.get("nextPageCursor")
        if not next_page_cursor:
            break
        # Be polite to the 20/min limit when paging
        time.sleep(0.35)

    return results


def _is_downloadable(raw: dict) -> bool:
    if SKIP_IF_PARENT and raw.get("parent_id"):
        return False
    category = str(raw.get("category") or "")
    return category in DOWNLOADABLE_CATEGORIES


def fetch_latest_documents(
    *,
    locations: Sequence[str] = DEFAULT_LOCATIONS,
    updated_after: Optional[str] = None,
    max_documents: int = 25,
    with_html: bool = True,
) -> List[ReaderDocument]:
    """
    Fetch recent top-level documents from the given Reader locations.

    Deduplicates by id across locations. Newest-first by saved_at/updated_at.
    """
    seen: set[str] = set()
    collected: List[ReaderDocument] = []

    for location in locations:
        raw_docs = list_documents(
            location=location,
            updated_after=updated_after,
            with_html=with_html,
            with_raw_source=True,
            limit=min(max_documents, 100),
            max_pages=max(1, (max_documents // 100) + 1),
        )
        for raw in raw_docs:
            if not _is_downloadable(raw):
                continue
            doc_id = str(raw.get("id") or "")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            collected.append(ReaderDocument.from_api(raw))

    def sort_key(d: ReaderDocument) -> str:
        return d.saved_at or d.updated_at or ""

    collected.sort(key=sort_key, reverse=True)
    return collected[:max_documents]


def _safe_filename(title: str, doc_id: str, ext: str) -> str:
    """Build a CrossPoint-friendly filename (ASCII, no path separators)."""
    base = re.sub(r"[^\w\s\-]+", "", title, flags=re.UNICODE)
    base = re.sub(r"\s+", "_", base.strip())[:60].strip("_")
    if not base:
        base = "article"
    short_id = doc_id[-8:] if len(doc_id) > 8 else doc_id
    return f"{base}_{short_id}.{ext.lstrip('.')}"


def _wrap_xhtml(title: str, author: str, body_html: str, source_url: str = "") -> str:
    """Wrap Reader HTML fragments into a minimal XHTML document."""
    safe_title = escape(title)
    safe_author = escape(author)
    # Reader returns HTML fragments; strip scripts and normalize void tags lightly.
    cleaned = re.sub(
        r"<script\b[^>]*>.*?</script>",
        "",
        body_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r"<style\b[^>]*>.*?</style>",
        "",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    meta = ""
    if source_url:
        meta = f'<p class="source"><a href="{escape(source_url)}">{escape(source_url)}</a></p>'

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head>
  <title>{safe_title}</title>
  <meta http-equiv="Content-Type" content="application/xhtml+xml; charset=utf-8"/>
  <style type="text/css">
    body {{ font-family: serif; line-height: 1.45; margin: 1em; }}
    h1 {{ font-size: 1.4em; margin-bottom: 0.2em; }}
    .byline {{ color: #444; font-size: 0.95em; margin-bottom: 1.2em; }}
    .source {{ font-size: 0.85em; word-break: break-all; }}
    img {{ max-width: 100%; height: auto; }}
  </style>
</head>
<body>
  <h1>{safe_title}</h1>
  <p class="byline">{safe_author}</p>
  {meta}
  {cleaned}
</body>
</html>
"""


def build_epub(
    *,
    title: str,
    author: str,
    body_html: str,
    output_path: Path,
    source_url: str = "",
) -> Path:
    """
    Write a minimal EPUB 2 file CrossPoint can open.

    Uses only the standard library (zipfile).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    xhtml = _wrap_xhtml(title, author, body_html, source_url=source_url)
    book_id = f"reader-{abs(hash(title + author)) % 10_000_000}"
    safe_title = escape(title)
    safe_author = escape(author)

    container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
            xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:title>{safe_title}</dc:title>
    <dc:creator opf:role="aut">{safe_author}</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="BookId">{book_id}</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chapter"/>
  </spine>
</package>
"""
    toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="{book_id}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{safe_title}</text></docTitle>
  <navMap>
    <navPoint id="navPoint-1" playOrder="1">
      <navLabel><text>{safe_title}</text></navLabel>
      <content src="chapter.xhtml"/>
    </navPoint>
  </navMap>
</ncx>
"""

    with zipfile.ZipFile(output_path, "w") as zf:
        # mimetype must be first and stored (not deflated) per EPUB spec
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)
        zf.writestr("OEBPS/chapter.xhtml", xhtml.encode("utf-8"))

    return output_path


def _download_url(url: str, dest: Path) -> Path:
    """Download a remote file (e.g. Reader raw_source_url) to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "wallpaper-automation-reader/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())
    return dest


def export_document(doc: ReaderDocument, output_dir: Path) -> Optional[Path]:
    """
    Export one document to output_dir.

    Prefer native EPUB/PDF raw sources when available; otherwise build an EPUB
    from html_content. Returns the written path, or None if nothing usable.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_url = doc.raw_source_url or ""
    lower_url = raw_url.lower().split("?", 1)[0]

    if raw_url and (lower_url.endswith(".epub") or doc.category == "epub"):
        path = output_dir / _safe_filename(doc.title, doc.id, "epub")
        log.info("Downloading EPUB source: %s", doc.title)
        return _download_url(raw_url, path)

    if raw_url and (lower_url.endswith(".pdf") or doc.category == "pdf"):
        path = output_dir / _safe_filename(doc.title, doc.id, "pdf")
        log.info("Downloading PDF source: %s", doc.title)
        return _download_url(raw_url, path)

    if not doc.html_content or len(doc.html_content.strip()) < 40:
        # Fall back to a short text stub so the item still appears on device
        if not doc.summary and not doc.source_url:
            log.warning("Skipping %s — no HTML/content available", doc.id)
            return None
        body = f"<p>{html_lib.escape(doc.summary or 'No content available.')}</p>"
    else:
        body = doc.html_content

    path = output_dir / _safe_filename(doc.title, doc.id, "epub")
    log.info("Building EPUB: %s", doc.title)
    return build_epub(
        title=doc.title,
        author=doc.author,
        body_html=body,
        output_path=path,
        source_url=doc.source_url,
    )


@dataclass
class SyncState:
    """Persisted sync cursor + already-exported document ids."""
    synced_ids: List[str]
    last_sync_at: str

    @classmethod
    def load(cls, path: Path) -> "SyncState":
        if not path.exists():
            return cls(synced_ids=[], last_sync_at="")
        try:
            data = json.loads(path.read_text())
            return cls(
                synced_ids=list(data.get("synced_ids") or []),
                last_sync_at=str(data.get("last_sync_at") or ""),
            )
        except (json.JSONDecodeError, OSError):
            return cls(synced_ids=[], last_sync_at="")

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "synced_ids": self.synced_ids[-2000:],  # cap growth
            "last_sync_at": self.last_sync_at,
        }, indent=2) + "\n")


def sync_articles(
    output_dir: Path,
    state_path: Path,
    *,
    locations: Sequence[str] = DEFAULT_LOCATIONS,
    max_documents: int = 25,
    updated_after: Optional[str] = None,
    force: bool = False,
) -> List[Path]:
    """
    Download new Reader articles to output_dir.

    Skips document ids already recorded in state_path unless force=True.
    On first run (empty state), only the newest max_documents are pulled —
    not the entire library.
    """
    state = SyncState.load(state_path)
    already = set(state.synced_ids) if not force else set()

    # Incremental sync when we have a previous cursor
    cursor = updated_after
    if cursor is None and state.last_sync_at and not force:
        cursor = state.last_sync_at

    docs = fetch_latest_documents(
        locations=locations,
        updated_after=cursor,
        max_documents=max_documents if cursor else max_documents,
        with_html=True,
    )

    exported: List[Path] = []
    for doc in docs:
        if doc.id in already:
            continue
        try:
            path = export_document(doc, output_dir)
        except Exception as exc:
            log.warning("Failed to export %s (%s): %s", doc.id, doc.title[:60], exc)
            continue
        if path is None:
            continue
        exported.append(path)
        if doc.id not in state.synced_ids:
            state.synced_ids.append(doc.id)

    state.last_sync_at = datetime.now(timezone.utc).isoformat()
    state.save(state_path)
    return exported


def parse_locations(value: str) -> List[str]:
    """Parse comma-separated Reader locations from env."""
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or list(DEFAULT_LOCATIONS)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Download latest Readwise Reader articles as EPUBs")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "output" / "reader",
        help="Directory for exported EPUBs",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(__file__).parent.parent / "state" / "reader_sync.json",
        help="Sync state file (tracks downloaded ids)",
    )
    parser.add_argument(
        "--locations",
        type=str,
        default=os.environ.get("READER_LOCATIONS", "new"),
        help="Comma-separated Reader locations (default: new)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=int(os.environ.get("READER_MAX_ARTICLES", "25")),
        help="Max articles to fetch (default: 25)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if already synced",
    )
    args = parser.parse_args()

    paths = sync_articles(
        args.output_dir,
        args.state,
        locations=parse_locations(args.locations),
        max_documents=args.max,
        force=args.force,
    )
    print(f"Exported {len(paths)} article(s) to {args.output_dir}")
    for p in paths:
        print(f"  {p.name}")
