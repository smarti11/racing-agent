#!/usr/bin/env python3
"""Passi MVP — English catalog tours + temporary session links."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PACKS = ROOT / "packs"
DATA = ROOT / "data"
DB_PATH = DATA / "sessions.db"
DEFAULT_TTL_HOURS = 48
PORT = int(os.environ.get("PASSI_PORT", "8100"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def db() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
          token TEXT PRIMARY KEY,
          tour_id TEXT NOT NULL,
          locale TEXT NOT NULL DEFAULT 'en',
          created_at TEXT NOT NULL,
          expires_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def load_catalog() -> dict:
    return json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))


def load_pack(tour_id: str) -> dict | None:
    catalog = load_catalog()
    for t in catalog["tours"]:
        if t["id"] == tour_id:
            path = PACKS / t["pack"]
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
    # allow direct pack id == filename stem
    path = PACKS / f"{tour_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def create_session(tour_id: str, ttl_hours: int = DEFAULT_TTL_HOURS, locale: str = "en") -> dict:
    if locale != "en":
        raise ValueError("MVP supports English only (locale=en).")
    pack = load_pack(tour_id)
    if not pack:
        raise ValueError(f"Unknown tour: {tour_id}")
    token = uuid.uuid4().hex[:16]
    now = utcnow()
    exp = now + timedelta(hours=ttl_hours)
    with db() as conn:
        conn.execute(
            "INSERT INTO sessions(token, tour_id, locale, created_at, expires_at) VALUES (?,?,?,?,?)",
            (token, tour_id, locale, now.isoformat(), exp.isoformat()),
        )
        conn.commit()
    return {
        "token": token,
        "tourId": tour_id,
        "locale": locale,
        "url": f"/t/{token}",
        "playerUrl": f"/static/player.html?token={token}",
        "expiresAt": exp.isoformat(),
        "ttlHours": ttl_hours,
    }


def get_session(token: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
    if not row:
        return None
    exp = datetime.fromisoformat(row["expires_at"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    expired = utcnow() >= exp
    return {
        "token": row["token"],
        "tourId": row["tour_id"],
        "locale": row["locale"],
        "createdAt": row["created_at"],
        "expiresAt": row["expires_at"],
        "expired": expired,
    }


class PassiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/sessions":
            try:
                data = self._read_json()
                tour_id = data.get("tourId") or data.get("tour_id")
                if not tour_id:
                    return self._json(400, {"error": "tourId required"})
                ttl = int(data.get("ttlHours") or DEFAULT_TTL_HOURS)
                ttl = max(1, min(ttl, 168))
                locale = data.get("locale") or "en"
                session = create_session(tour_id, ttl_hours=ttl, locale=locale)
                return self._json(201, session)
            except ValueError as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:
                return self._json(500, {"error": str(e)})
        return self._json(404, {"error": "not found"})

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/catalog":
            return self._json(200, load_catalog())

        if path.startswith("/api/packs/"):
            tour_id = path.split("/api/packs/", 1)[1].strip("/")
            pack = load_pack(tour_id)
            if not pack:
                return self._json(404, {"error": "pack not found"})
            return self._json(200, pack)

        if path.startswith("/api/sessions/"):
            token = path.split("/api/sessions/", 1)[1].strip("/")
            sess = get_session(token)
            if not sess:
                return self._json(404, {"error": "session not found"})
            if sess["expired"]:
                return self._json(410, {"error": "session expired", "session": sess})
            pack = load_pack(sess["tourId"])
            return self._json(200, {"session": sess, "pack": pack})

        # Pretty session entry: /t/{token} → redirect to player
        if path.startswith("/t/"):
            token = path[3:].strip("/").split("/")[0]
            sess = get_session(token)
            self.send_response(302 if sess and not sess["expired"] else 302)
            if sess and not sess["expired"]:
                self.send_header("Location", f"/static/player.html?token={token}")
            else:
                self.send_header("Location", f"/static/expired.html?token={token}")
            self.end_headers()
            return

        if path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/static/index.html")
            self.end_headers()
            return

        return super().do_GET()

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


def main():
    db().close()
    # Serve from ROOT so /media and /static and /packs work
    os.chdir(ROOT)
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), PassiHandler)
    print(f"Passi MVP on http://0.0.0.0:{PORT}")
    print(f"  Catalog:  http://127.0.0.1:{PORT}/")
    print(f"  API:      POST /api/sessions  {{\"tourId\":\"florence-classic-en\"}}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
