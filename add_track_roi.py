text = open("db/database.py").read()

new_func = '''

def get_track_roi_by_confidence() -> dict:
    """ROI by track + confidence tier for Pick #1."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            SELECT r.track_name, ap.confidence,
                   COUNT(*) as races,
                   SUM(CASE WHEN ap.result='WIN' THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN ap.result IN ('WIN','PLACE','SHOW') THEN 1 ELSE 0 END) as wps,
                   SUM(CASE WHEN ap.result='WIN' THEN res.winner_win_payout ELSE 0 END) as win_returns
            FROM agent_picks ap
            JOIN races r ON r.id = ap.race_id
            LEFT JOIN results res ON res.race_id = ap.race_id
            WHERE ap.rank=1 AND ap.result IS NOT NULL
            GROUP BY r.track_name, ap.confidence
            ORDER BY r.track_name, ap.confidence
        """).fetchall()
        result = {}
        for row in rows:
            track = row["track_name"]
            conf = row["confidence"] or "NONE"
            if track not in result:
                result[track] = {}
            races = row["races"]
            wagered = races * 2.00
            returned = row["win_returns"] or 0
            roi = ((returned - wagered) / wagered * 100) if wagered else 0
            result[track][conf] = {
                "races": races, "wins": row["wins"], "wps": row["wps"],
                "win_pct": round(row["wins"]/races*100, 1),
                "wps_pct": round(row["wps"]/races*100, 1),
                "wagered": wagered, "returned": returned,
                "roi_pct": round(roi, 1),
            }
        return result
    except Exception as e:
        logger.warning(f"Track ROI error: {e}")
        return {}
    finally:
        conn.close()


'''

marker = "def get_pick_record():"
if marker in text and "get_track_roi_by_confidence" not in text:
    text = text.replace(marker, new_func + marker)
    open("db/database.py", "w").write(text)
    print("Added get_track_roi_by_confidence")
else:
    print("Already present or marker missing")
