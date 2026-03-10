"""
╔══════════════════════════════════════════════════════════════╗
║   BRAINROT NETWORK — Central Server v1.0                    ║
║   Deploy on Render.com (free tier)                          ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import threading
import time
import uuid

app = Flask(__name__)
CORS(app)

# ══════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════
API_KEY        = "BRAINROT_SECRET_2024"   # ← שנה לסיסמה שלך!
PLACE_ID       = 109983668079237
EXPIRY_MINUTES = 8                         # כמה דקות שרת נשאר בלוח
MAX_SERVERS    = 200                       # מקסימום שרתים בזיכרון
# ══════════════════════════════════════════════════════════════════

# ── מסד נתונים בזיכרון ───────────────────────────────────────────
# { job_id: { job_id, brainrots, players, reporter, value, timestamp } }
servers_db: dict = {}
db_lock = threading.Lock()
stats = {
    "total_reports": 0,
    "total_reporters": set(),
    "uptime": datetime.now(),
}

# ── ניקוי שרתים ישנים ────────────────────────────────────────────
def cleanup_loop():
    while True:
        now = datetime.now()
        with db_lock:
            expired = [
                jid for jid, data in servers_db.items()
                if now - data["timestamp"] > timedelta(minutes=EXPIRY_MINUTES)
            ]
            for jid in expired:
                del servers_db[jid]
        time.sleep(30)

threading.Thread(target=cleanup_loop, daemon=True).start()

# ── AUTH ──────────────────────────────────────────────────────────
def check_auth():
    key = request.headers.get("X-API-Key") or request.args.get("key")
    return key == API_KEY

# ══════════════════════════════════════════════════════════════════
#  API ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name":    "Brainrot Network Server",
        "version": "1.0",
        "status":  "online",
        "servers": len(servers_db),
    })

# ── POST /report — סקריפט שולח דיווח ─────────────────────────────
@app.route("/report", methods=["POST"])
def report():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    data = request.json
    if not data:
        return jsonify({"error": "no data"}), 400

    job_id    = data.get("job_id")
    brainrots = data.get("brainrots", [])   # [{ name, price, value, tier }]
    players   = data.get("players", 0)
    reporter  = data.get("reporter", "unknown")

    if not job_id or not brainrots:
        return jsonify({"error": "missing fields"}), 400

    # חשב ערך מקסימלי
    max_value = max((b.get("value", 0) for b in brainrots), default=0)

    with db_lock:
        servers_db[job_id] = {
            "job_id":    job_id,
            "brainrots": brainrots,
            "players":   players,
            "reporter":  reporter,
            "max_value": max_value,
            "timestamp": datetime.now(),
            "join_url":  f"roblox://experiences/start?placeId={PLACE_ID}&gameInstanceId={job_id}",
        }

        stats["total_reports"] += 1
        stats["total_reporters"].add(reporter)

        # הגבל גודל
        if len(servers_db) > MAX_SERVERS:
            oldest = sorted(servers_db.items(), key=lambda x: x[1]["timestamp"])[0][0]
            del servers_db[oldest]

    return jsonify({"status": "ok", "job_id": job_id})

# ── GET /servers — קבל רשימת שרתים ──────────────────────────────
@app.route("/servers", methods=["GET"])
def get_servers():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401

    min_value = int(request.args.get("min", 0))

    with db_lock:
        result = [
            s for s in servers_db.values()
            if s["max_value"] >= min_value
        ]

    # מיין לפי ערך יורד
    result.sort(key=lambda x: x["max_value"], reverse=True)

    # המר timestamps לstring
    for s in result:
        s = dict(s)
        s["timestamp"] = s["timestamp"].isoformat()

    return jsonify({
        "servers": result,
        "count":   len(result),
        "total_reporters": len(stats["total_reporters"]),
    })

# ── GET /stats ────────────────────────────────────────────────────
@app.route("/stats", methods=["GET"])
def get_stats():
    uptime = datetime.now() - stats["uptime"]
    return jsonify({
        "servers_active":   len(servers_db),
        "total_reports":    stats["total_reports"],
        "unique_reporters": len(stats["total_reporters"]),
        "uptime_hours":     round(uptime.total_seconds() / 3600, 1),
    })

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"[Server] Starting on port {port}")
    app.run(host="0.0.0.0", port=port)
