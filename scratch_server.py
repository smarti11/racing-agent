#!/usr/bin/env python3
"""
Scratch Override Server
========================
Tiny HTTP server that accepts manual scratch flags from the dashboard.
Listens on port 8082, accepts POST /scratch with JSON body.
Updates entries.scratched and logs to manual_scratches audit table.
Touches a flag file that the main agent watches to force dashboard regen.
"""

import json
import sqlite3
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

DB_PATH = Path.home() / "agents/racing-agent/db/racing.db"
REGEN_FLAG = Path.home() / "agents/racing-agent/.regen_now"
LOG_PATH = Path.home() / "agents/racing-agent/logs/scratch_server.log"


def log(msg):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with open(LOG_PATH, "a") as f:
        f.write(f"{ts}  {msg}\n")
    print(f"{ts}  {msg}", flush=True)


def init_audit_table():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS manual_scratches (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            race_id      INTEGER NOT NULL,
            program_num  INTEGER NOT NULL,
            horse_name   TEXT,
            track_name   TEXT,
            race_num     INTEGER,
            race_date    TEXT,
            flagged_ts   TEXT NOT NULL,
            source       TEXT DEFAULT 'manual_button'
        )
    """)
    conn.commit()
    conn.close()


def mark_scratch(race_id, program_num):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    info = conn.execute("""
        SELECT 
            e.horse_name,
            e.scratched AS already_scratched,
            r.track_name,
            r.race_num,
            r.race_date
        FROM entries e
        JOIN races r ON e.race_id = r.id
        WHERE e.race_id = ? AND e.program_num = ?
    """, (race_id, program_num)).fetchone()

    if not info:
        conn.close()
        return None, "Horse not found in entries"

    if info["already_scratched"]:
        conn.close()
        return dict(info), "Already scratched"

    now = datetime.now().isoformat(timespec="seconds")
    conn.execute("""
        UPDATE entries 
        SET scratched = 1, scratch_time = ? 
        WHERE race_id = ? AND program_num = ?
    """, (now, race_id, program_num))

    conn.execute("""
        INSERT INTO manual_scratches 
            (race_id, program_num, horse_name, track_name, race_num, race_date, flagged_ts, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'manual_button')
    """, (
        race_id, program_num,
        info["horse_name"], info["track_name"], info["race_num"], info["race_date"],
        now
    ))

    conn.commit()
    conn.close()
    return dict(info), None


class ScratchHandler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(200, {"ok": True})

    def do_POST(self):
        if self.path != "/scratch":
            self._send(404, {"error": "Use POST /scratch"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(raw)
            race_id = int(data.get("race_id"))
            program_num = int(data.get("program_num"))
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            self._send(400, {"error": f"Bad request: {e}"})
            return

        info, err = mark_scratch(race_id, program_num)
        if err and err != "Already scratched":
            self._send(404, {"error": err})
            return

        try:
            REGEN_FLAG.touch()
        except Exception as e:
            log(f"WARN: could not touch regen flag: {e}")

        log(f"SCRATCHED: race_id={race_id} prog#{program_num} {info['horse_name']} ({info['track_name']} R{info['race_num']})")

        self._send(200, {
            "success": True,
            "race_id": race_id,
            "program_num": program_num,
            "horse_name": info["horse_name"],
            "track_name": info["track_name"],
            "race_num": info["race_num"],
            "already_scratched": err == "Already scratched",
        })

    def log_message(self, format, *args):
        return


def main():
    init_audit_table()
    log("Scratch server starting on port 8082")
    server = HTTPServer(("0.0.0.0", 8082), ScratchHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Scratch server stopped")


if __name__ == "__main__":
    main()
