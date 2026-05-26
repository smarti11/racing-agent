"""
Equibase PDF Chart Fetcher
===========================
Downloads and caches the daily PDF result charts from Equibase.

URL pattern: https://www.equibase.com/static/chart/PDF/{TRACK}{MMDDYY}USA.pdf
Example:     https://www.equibase.com/static/chart/PDF/PRX041426USA.pdf

The PDF contains ALL races for that track on that date, with full charts
including finishing times, fractional times, margins, and past performance
data — none of which is available in the mobile HTML results.

Cache location: ~/Documents/racing-agent/data/charts/{TRACK}_{YYYYMMDD}.pdf
"""

import os
import logging
import subprocess
import requests
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("racing_agent")

BASE_URL = "https://www.equibase.com/static/chart/PDF"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
}

CACHE_DIR = Path.home() / "Documents/racing-agent/data/charts"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_chart_pdf(track_code: str, date_str: str, force: bool = False) -> Path:
    """
    Download PDF chart for a track/date. Cached to disk.

    Args:
        track_code: e.g. "PRX", "KEE", "AQU"
        date_str:   YYYYMMDD format (e.g. "20260414")
        force:      if True, re-download even if cached

    Returns:
        Path to the cached PDF, or None if unavailable.
    """
    # Parse date to MMDDYY for Equibase URL
    try:
        dt = datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        logger.warning(f"Invalid date format: {date_str}")
        return None

    mmddyy = dt.strftime("%m%d%y")
    url = f"{BASE_URL}/{track_code}{mmddyy}USA.pdf"
    cache_path = CACHE_DIR / f"{track_code}_{date_str}.pdf"

    # Return cached version if available
    if cache_path.exists() and not force:
        logger.debug(f"Chart cached: {track_code} {date_str}")
        return cache_path

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 404:
            logger.info(f"No chart available: {track_code} {date_str}")
            return None
        resp.raise_for_status()

        # Sanity check — valid PDF starts with %PDF
        if not resp.content.startswith(b"%PDF"):
            logger.warning(f"Chart response not a PDF: {track_code} {date_str}")
            return None

        cache_path.write_bytes(resp.content)
        logger.info(f"Chart fetched: {track_code} {date_str} ({len(resp.content)} bytes)")
        return cache_path

    except Exception as e:
        logger.warning(f"Chart fetch error {track_code} {date_str}: {e}")
        return None


def pdf_to_text(pdf_path: Path) -> str:
    """
    Extract text from PDF using pdftotext (poppler).
    Returns the full text content, or empty string on failure.
    """
    if not pdf_path or not pdf_path.exists():
        return ""

    try:
        # -layout preserves column structure which helps parsing
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.warning(f"pdftotext error: {result.stderr}")
            return ""
        return result.stdout
    except FileNotFoundError:
        logger.error("pdftotext not installed. Run: brew install poppler")
        return ""
    except Exception as e:
        logger.warning(f"PDF extraction error: {e}")
        return ""


def get_chart_text(track_code: str, date_str: str) -> str:
    """Convenience: fetch PDF and return extracted text."""
    pdf_path = fetch_chart_pdf(track_code, date_str)
    if not pdf_path:
        return ""
    return pdf_to_text(pdf_path)


if __name__ == "__main__":
    # Test harness
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    text = get_chart_text("PRX", "20260414")
    if text:
        print(f"Extracted {len(text)} chars")
        print(text[:500])
    else:
        print("Failed to fetch chart")
