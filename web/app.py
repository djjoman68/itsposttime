"""Web UI for the LED odds board - http://<pi-name>.local:8080

Same approach as the plane tracker: a small Flask app started alongside the
display. It edits config/config.json and secrets.json; the display picks up
race settings within a second, other settings after a restart.
"""
import io
import json
import os
import subprocess
import sys
import threading
import time

from flask import Flask, jsonify, render_template, request, send_file

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
import config  # noqa: E402
from utilities.race_render import led_preview  # noqa: E402

SERVICE = "odds-board"
CFG_PATH = os.path.join(BASE_DIR, "config", "config.json")
SEC_PATH = os.path.join(BASE_DIR, "config", "secrets.json")
STATUS_DIR = "/dev/shm/odds-board" if os.path.isdir("/dev/shm") else os.path.join(BASE_DIR, ".cache")
STATUS_FILE = os.path.join(STATUS_DIR, "status.json")
FRAME_FILE = os.path.join(STATUS_DIR, "board.png")

app = Flask(__name__)


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _full_config():
    """Saved config with any missing settings filled from the defaults."""
    cfg = _load(CFG_PATH)
    return {sec: {**vals, **cfg.get(sec, {})} for sec, vals in config.DEFAULT_CONFIG.items()}


def _mask(v):
    return v[:4] + "****" + v[-4:] if isinstance(v, str) and len(v) > 8 else v


# ---------- pages ----------
@app.get("/")
def home():
    return render_template("index.html")


@app.get("/config")
def config_page():
    return render_template("config.html")


@app.get("/logs")
def logs_page():
    return render_template("logs.html")


# ---------- API ----------
@app.get("/api/status")
def api_status():
    status = _load(STATUS_FILE)
    if status:
        status["age_seconds"] = int(time.time() - os.path.getmtime(STATUS_FILE))
    racing = _full_config()["racing"]
    return jsonify({"status": status or None, "racing": racing})


@app.get("/board.png")
def board_png():
    """Latest picture of the panel (race board or clock & weather), enlarged to look like the LEDs."""
    from PIL import Image
    if not os.path.exists(FRAME_FILE):
        return ("", 204)
    img = led_preview(Image.open(FRAME_FILE).convert("RGB"), dot=8)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    resp = send_file(buf, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/config")
def config_get():
    sec = _load(SEC_PATH)
    return jsonify({"config": _full_config(), "secrets": {k: _mask(v) for k, v in sec.items()}})


@app.post("/api/config")
def config_save():
    data = request.get_json(force=True) or {}
    try:
        if "config" in data:
            merged = _full_config()
            for section, vals in data["config"].items():
                if section in merged and isinstance(vals, dict):
                    merged[section].update(vals)
            _save(CFG_PATH, merged)
        if "secrets" in data:
            existing = _load(SEC_PATH)
            for k, v in data["secrets"].items():
                if isinstance(v, str) and "****" in v:
                    continue          # unchanged masked value
                existing[k] = v.strip() if isinstance(v, str) else v
            _save(SEC_PATH, existing)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})


@app.post("/api/restart")
def api_restart():
    def _do():
        time.sleep(0.5)
        subprocess.run(["sudo", "systemctl", "restart", SERVICE], capture_output=True)
    threading.Thread(target=_do, daemon=True).start()
    return jsonify({"ok": True})


@app.post("/api/shutdown")
def api_shutdown():
    """Shut the Pi down so it can be unplugged without risking the SD card."""
    try:
        # Same passwordless sudo the Restart button relies on; check first so the page can say if it's missing
        allowed = subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        allowed = False
    if not allowed:
        return jsonify({"ok": False, "error": "The Pi wouldn't allow it. Connect to the Pi and type: sudo shutdown -h now"}), 500

    def _do():
        time.sleep(1)    # let the page get its reply first
        subprocess.run(["sudo", "-n", "systemctl", "poweroff"], capture_output=True)
    threading.Thread(target=_do, daemon=True).start()
    return jsonify({"ok": True})


@app.get("/api/system")
def api_system():
    out = {}
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            out["cpu_temp_c"] = round(int(f.read().strip()) / 1000, 1)
    except Exception:
        out["cpu_temp_c"] = None
    try:
        with open("/proc/uptime") as f:
            out["uptime_secs"] = int(float(f.read().split()[0]))
    except Exception:
        out["uptime_secs"] = None
    return jsonify(out)


@app.get("/api/logs")
def api_logs():
    n = str(min(int(request.args.get("n", 200)), 2000))
    try:
        r = subprocess.run(["journalctl", "-u", f"{SERVICE}.service", "--no-pager", "-o", "short-iso", "-n", n],
                           capture_output=True, text=True, timeout=10)
        return jsonify({"lines": r.stdout.splitlines(), "error": None})
    except Exception as e:
        return jsonify({"lines": [], "error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
