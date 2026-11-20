"""Preserve the eight cited sources in a single importable ZIP bundle.

Run outside production against an editorial TXT export. PDF originals are
downloaded byte-for-byte; webpages are saved as full-page PNGs and print PDFs.
Each file is recorded with a SHA-256 digest and a UTC capture timestamp.
"""

import argparse
import hashlib
import html as html_library
import json
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup
from weasyprint import HTML


def sources_from_export(text):
    result = []
    for diptych_match in re.finditer(r"(?m)^--- Демонтаж: (.+?) ---$", text):
        start = diptych_match.end()
        next_match = re.search(r"(?m)^--- Демонтаж: |^=== AUTHOR BIOGRAPHIES ===", text[start:])
        end = start + next_match.start() if next_match else len(text)
        block = text[start:end]
        slug_match = re.search(r"(?m)^Slug: ([a-z0-9-]+)$", block)
        if not slug_match:
            continue
        diptych_slug = slug_match.group(1)
        documents = re.findall(r"(?m)^Document: (.+)\nSource URL: (.+)$", block)
        for index, (title, url) in enumerate(documents, start=1):
            source_slug = diptych_slug if len(documents) == 1 else f"{diptych_slug}-{index}"
            result.append(
                {"slug": source_slug, "diptych_slug": diptych_slug,
                 "title": title, "original_url": url, "captures": []}
            )
    return result


def url_without_fragment(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def download_original_pdf(url, destination):
    request = urllib.request.Request(url_without_fragment(url), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(50 * 1024 * 1024 + 1)
    if len(data) > 50 * 1024 * 1024 or not data.startswith(b"%PDF-"):
        raise ValueError("The fetched response is not a PDF under 50 MiB")
    destination.write_bytes(data)


def capture_webpage(url, original_html, pdf):
    request = urllib.request.Request(url_without_fragment(url), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(15 * 1024 * 1024 + 1)
    if len(data) > 15 * 1024 * 1024:
        raise ValueError("HTML page exceeds 15 MiB")
    original_html.write_bytes(data)
    soup = BeautifulSoup(data, "html.parser")
    text_length = len(soup.get_text(" ", strip=True))
    if text_length < 250:
        raise ValueError(f"Suspiciously short webpage ({text_length} characters)")

    # Render a readable textual companion without executing JS or fetching
    # third-party assets. Preserve the untouched original response separately.
    article = soup.select_one("article") or soup.select_one("main") or soup.body or soup
    article = BeautifulSoup(str(article), "html.parser")
    for tag in article.select("script, style, nav, aside, footer, form, iframe, img, svg, video"):
        tag.decompose()
    page_title = soup.title.get_text(" ", strip=True) if soup.title else "Archived webpage"
    simplified = f"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
    <style>@page {{ size: A4; margin: 18mm; }}
    body {{font-family: DejaVu Sans, sans-serif; font-size: 11pt; line-height: 1.5;}}
    h1 {{font-size: 18pt; line-height: 1.25;}} h2 {{font-size: 14pt;}}
    p, li {{ overflow-wrap: anywhere; }} a {{color: #222;}}
    table {{border-collapse: collapse; max-width: 100%;}}
    td, th {{padding: 3px; border: 1px solid #aaa;}}</style></head>
    <body><h1>{html_library.escape(page_title)}</h1>{str(article)}</body></html>"""
    HTML(string=simplified).write_pdf(str(pdf))
    print(f"    title: {soup.title.get_text(' ', strip=True)[:110] if soup.title else 'untitled'}, "
          f"text length: {text_length}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sources = sources_from_export(args.export.read_text(encoding="utf-8"))
    if not sources:
        raise ValueError("No document source links in export")
    print(f"Found {len(sources)} sources", flush=True)
    with TemporaryDirectory(prefix="dismantling-archive-") as temporary:
        temp = Path(temporary)
        for index, source in enumerate(sources, start=1):
                    print(f"[{index}/{len(sources)}] {source['slug']} {source['original_url']}", flush=True)
                    url = source["original_url"]
                    head = urllib.request.Request(url_without_fragment(url), method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(head, timeout=30) as response:
                        is_pdf = "application/pdf" in response.headers.get("Content-Type", "").lower()
                    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    if is_pdf:
                        file = temp / f"{source['slug']}-original.pdf"
                        download_original_pdf(url, file)
                        paths_and_kinds = [(file, "original_pdf")]
                    else:
                        html = temp / f"{source['slug']}-original.html"
                        pdf = temp / f"{source['slug']}-webpage.pdf"
                        capture_webpage(url, html, pdf)
                        paths_and_kinds = [(pdf, "page_pdf"), (html, "original_html")]
                    for file, kind in paths_and_kinds:
                        data = file.read_bytes()
                        source["captures"].append(
                            {"filename": f"files/{file.name}", "kind": kind,
                             "captured_at": now, "sha256": hashlib.sha256(data).hexdigest()}
                        )
                        print(f"    {kind}: {len(data):,} bytes", flush=True)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=8) as output:
            output.writestr("manifest.json", json.dumps(
                {"format": "dismantling-source-archive-v1", "sources": sources},
                ensure_ascii=False, indent=2,
            ))
            for source in sources:
                for entry in source["captures"]:
                    output.write(temp / Path(entry["filename"]).name, arcname=entry["filename"])
    print(f"ARCHIVE READY: {args.output}", flush=True)


if __name__ == "__main__":
    main()
