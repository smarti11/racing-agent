"""Publish dashboard/racing.html to S3 after each regen (uses Mac Mini aws CLI)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("racing_agent")


def publish_dashboard_to_s3(
    local_path: str,
    s3_uri: str,
    *,
    enabled: bool = True,
    cache_control: str = "no-cache, max-age=0",
    content_type: str = "text/html",
    timeout_sec: int = 120,
) -> bool:
    """Upload local dashboard HTML to S3. Returns True on success."""
    if not enabled:
        return False

    if not s3_uri or not s3_uri.startswith("s3://"):
        logger.warning(f"S3 publish skipped — invalid URI: {s3_uri!r}")
        return False

    path = Path(local_path)
    if not path.is_file():
        logger.warning(f"S3 publish skipped — file missing: {path}")
        return False

    aws = shutil.which("aws")
    if not aws:
        logger.warning("S3 publish skipped — aws CLI not found on PATH")
        return False

    cmd = [
        aws, "s3", "cp", str(path), s3_uri,
        "--cache-control", cache_control,
        "--content-type", content_type,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_sec, check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"S3 publish timed out after {timeout_sec}s → {s3_uri}")
        return False
    except Exception as e:
        logger.warning(f"S3 publish error: {e}")
        return False

    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        logger.warning(f"S3 publish failed (rc={result.returncode}): {err[:300]}")
        return False

    logger.info(f"Dashboard published → {s3_uri}")
    return True
