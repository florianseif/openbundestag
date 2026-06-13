"""Playwright-based downloader — invoked as a subprocess by extract.py.

Usage:
    python src/_pw_download.py modern <wahlperiode> <term_dir> <filterlist_url_tpl>
    python src/_pw_download.py legacy  <wahlperiode> <term_dir> <zip_url>
"""

import io
import re
import sys
import time
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def prime_session(ctx):
    page = ctx.new_page()
    page.goto("https://www.bundestag.de/services/opendata", wait_until="networkidle", timeout=30000)
    page.close()


def download_modern(wahlperiode: int, term_dir: Path, url_tpl: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        prime_session(ctx)

        xml_links: list[str] = []
        offset = 0
        page = ctx.new_page()
        print(f"[extract] Scraping session links for term {wahlperiode}…", flush=True)
        while True:
            page.goto(url_tpl.format(offset), wait_until="networkidle", timeout=30000)
            soup = BeautifulSoup(page.content(), "lxml")
            found = soup.find_all("a", href=re.compile(r"\.xml$"))
            if not found:
                break
            xml_links.extend(a["href"] for a in found)
            offset += len(found)
        page.close()

        total = len(xml_links)
        print(f"[extract] Found {total} sessions — downloading…", flush=True)

        dl_page = ctx.new_page()
        for i, href in enumerate(xml_links, 1):
            url = href if href.startswith("http") else "https://www.bundestag.de" + href
            m = re.search(r"(\d{5})\.xml$", url)
            if not m:
                continue
            session_id = m.group(1)
            out_path = term_dir / f"{session_id}.xml"
            if out_path.exists():
                print(f"  [{i}/{total}] {session_id}.xml — cached", flush=True)
                continue

            try:
                with dl_page.expect_download(timeout=60000) as dl_info:
                    dl_page.goto(url, wait_until="commit", timeout=60000)
                download = dl_info.value
                download.save_as(out_path)
                print(f"  [{i}/{total}] {session_id}.xml — OK (download)", flush=True)
            except Exception:
                content = dl_page.content()
                if any(tag in content for tag in ("<rede>", "<DOKUMENT>", "dbtplenarprotokoll")):
                    out_path.write_text(content, encoding="utf-8")
                    print(f"  [{i}/{total}] {session_id}.xml — OK (page)", flush=True)
                else:
                    print(f"  [{i}/{total}] {session_id}.xml — SKIPPED (unexpected content)", flush=True)
            time.sleep(0.3)
        dl_page.close()
        browser.close()

    print(f"[extract] Term {wahlperiode} complete → {term_dir}", flush=True)


def download_legacy(wahlperiode: int, term_dir: Path, zip_url: str) -> None:
    if any(term_dir.iterdir()):
        print(f"[extract] Term {wahlperiode} already extracted → {term_dir}", flush=True)
        return

    print(f"[extract] Downloading ZIP for term {wahlperiode}…", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        )
        prime_session(ctx)
        page = ctx.new_page()
        with page.expect_download(timeout=300000) as dl_info:
            try:
                page.goto(zip_url, wait_until="commit", timeout=60000)
            except Exception as e:
                if "Download is starting" not in str(e):
                    raise
        download = dl_info.value
        zip_bytes = Path(download.path()).read_bytes()
        page.close()
        browser.close()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        z.extractall(term_dir)
    print(f"[extract] Term {wahlperiode} complete → {term_dir}", flush=True)


if __name__ == "__main__":
    mode = sys.argv[1]
    wahlperiode = int(sys.argv[2])
    term_dir = Path(sys.argv[3])
    term_dir.mkdir(parents=True, exist_ok=True)

    if mode == "modern":
        url_tpl = sys.argv[4]
        download_modern(wahlperiode, term_dir, url_tpl)
    elif mode == "legacy":
        zip_url = sys.argv[4]
        download_legacy(wahlperiode, term_dir, zip_url)
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(1)
