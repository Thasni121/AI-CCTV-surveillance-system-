
import os, json, uuid, threading, time
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from cctv_core.processor import process_video
from cctv_core.config import load_config, save_config
from cctv_core.events import read_events, summarize_events

ROOT = Path(__file__).resolve().parent
CFG = load_config(ROOT / "config.json")
app = Flask(__name__)
app.secret_key = os.environ.get("CCTV_SECRET_KEY", "change-this-development-key")
app.config["MAX_CONTENT_LENGTH"] = int(CFG.get("max_upload_mb", 500)) * 1024 * 1024
ALLOWED = {".mp4", ".avi", ".mov", ".mkv", ".mpeg", ".mpg"}
JOBS = {}
LOCK = threading.Lock()

for folder in ("uploads", "outputs", "evidence", "data"):
    (ROOT / folder).mkdir(exist_ok=True)

def _worker(job_id, video_path, settings):
    with LOCK:
        JOBS[job_id]["status"] = "processing"
    try:
        result = process_video(video_path, ROOT, settings, job_id)
        with LOCK:
            JOBS[job_id].update(status="completed", result=result, finished=datetime.now().isoformat())
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status="failed", error=str(exc), finished=datetime.now().isoformat())

@app.route("/")
def index():
    events = read_events(ROOT / "data" / "events.jsonl", limit=15)
    summary = summarize_events(read_events(ROOT / "data" / "events.jsonl", limit=5000))
    output_files = sorted([p.name for p in (ROOT / "outputs").glob("*_annotated.mp4")], reverse=True)[:10]
    return render_template("index.html", events=events, summary=summary, outputs=output_files, config=CFG)

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("video")
    if not file or not file.filename:
        flash("Choose a video file first.", "error")
        return redirect(url_for("index"))
    name = secure_filename(file.filename)
    if Path(name).suffix.lower() not in ALLOWED:
        flash("Unsupported file type. Use MP4, AVI, MOV, MKV, MPEG or MPG.", "error")
        return redirect(url_for("index"))
    job_id = uuid.uuid4().hex[:10]
    saved = ROOT / "uploads" / f"{job_id}_{name}"
    file.save(saved)
    settings = dict(CFG)
    settings["job_id"] = job_id
    settings["video_name"] = name
    with LOCK:
        JOBS[job_id] = {"id": job_id, "name": name, "status": "queued", "created": datetime.now().isoformat()}
    threading.Thread(target=_worker, args=(job_id, str(saved), settings), daemon=True).start()
    return redirect(url_for("job_page", job_id=job_id))

@app.route("/job/<job_id>")
def job_page(job_id):
    job = JOBS.get(job_id)
    if not job:
        flash("This job is not in the current server session. Check the output folder for completed files.", "error")
        return redirect(url_for("index"))
    return render_template("job.html", job=job)

@app.route("/api/job/<job_id>")
def api_job(job_id):
    return jsonify(JOBS.get(job_id, {"id": job_id, "status": "unknown"}))

@app.route("/events")
def events_page():
    return render_template("events.html", events=read_events(ROOT / "data" / "events.jsonl", limit=300),
                           summary=summarize_events(read_events(ROOT / "data" / "events.jsonl", limit=5000)))

@app.route("/settings", methods=["GET", "POST"])
def settings():
    global CFG
    if request.method == "POST":
        CFG["confidence"] = max(0.05, min(0.99, float(request.form.get("confidence", CFG["confidence"]))))
        CFG["frame_stride"] = max(1, int(request.form.get("frame_stride", CFG["frame_stride"])))
        CFG["snapshot_interval_sec"] = max(0.5, float(request.form.get("snapshot_interval_sec", CFG["snapshot_interval_sec"])))
        CFG["enable_low_light"] = request.form.get("enable_low_light") == "on"
        CFG["enable_vehicle_ocr"] = request.form.get("enable_vehicle_ocr") == "on"
        CFG["restricted_zone_enabled"] = request.form.get("restricted_zone_enabled") == "on"
        CFG["zone_x1_ratio"] = max(0.0, min(1.0, float(request.form.get("zone_x1_ratio", CFG.get("zone_x1_ratio", 0.35)))))
        CFG["zone_y1_ratio"] = max(0.0, min(1.0, float(request.form.get("zone_y1_ratio", CFG.get("zone_y1_ratio", 0.30)))))
        CFG["zone_x2_ratio"] = max(0.0, min(1.0, float(request.form.get("zone_x2_ratio", CFG.get("zone_x2_ratio", 0.85)))))
        CFG["zone_y2_ratio"] = max(0.0, min(1.0, float(request.form.get("zone_y2_ratio", CFG.get("zone_y2_ratio", 0.85)))))
        CFG["loitering_threshold_sec"] = max(3, int(request.form.get("loitering_threshold_sec", CFG.get("loitering_threshold_sec", 15))))
        CFG["enable_email_alerts"] = request.form.get("enable_email_alerts") == "on"
        CFG["enable_sms_alerts"] = request.form.get("enable_sms_alerts") == "on"
        save_config(ROOT / "config.json", CFG)
        flash("Settings saved. They apply to newly submitted videos.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html", config=CFG)

@app.route("/outputs/<path:filename>")
def output_file(filename):
    return send_from_directory(ROOT / "outputs", filename, as_attachment=False)

@app.route("/evidence/<path:filename>")
def evidence_file(filename):
    return send_from_directory(ROOT / "evidence", filename, as_attachment=False)

@app.route("/api/alerts")
def api_alerts():
    events = read_events(ROOT / "data" / "events.jsonl", limit=300)
    alerts = [e for e in events if e.get("severity") in {"HIGH", "CRITICAL"}]
    return jsonify(alerts[:20])

@app.route("/health")
def health():
    return jsonify({"status": "ok", "model": CFG.get("model_name"), "note": "Prototype health endpoint"})

if __name__ == "__main__":
    print("AI CCTV Surveillance System starting at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
