
import json
from pathlib import Path

DEFAULTS = {
    "model_name": "yolo11n.pt",
    "confidence": 0.35,
    "iou": 0.45,
    "frame_stride": 1,
    "snapshot_interval_sec": 2.0,
    "enable_low_light": False,
    "enable_vehicle_ocr": False,
    "max_upload_mb": 500,
    "classes": ["person", "bicycle", "car", "motorcycle", "bus", "truck"],
    "zone_line_y_ratio": 0.65,
    "restricted_zone_enabled": True,
    "zone_x1_ratio": 0.35,
    "zone_y1_ratio": 0.30,
    "zone_x2_ratio": 0.85,
    "zone_y2_ratio": 0.85,
    "loitering_threshold_sec": 15,
    "enable_email_alerts": False,
    "enable_sms_alerts": False,
    "crowd_threshold": 8,
    "event_cooldown_sec": 5,
    "ocr_engine": "easyocr",
    "face_recognition_api_url": "",
    "face_recognition_api_key_env": "FR_API_KEY",
    "webhook_url_env": "CCTV_ALERT_WEBHOOK_URL",
    "rtsp_sources": []
}

def load_config(path):
    path = Path(path)
    if not path.exists():
        save_config(path, DEFAULTS.copy())
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {**DEFAULTS, **data}
    except Exception:
        return DEFAULTS.copy()

def save_config(path, config):
    Path(path).write_text(json.dumps(config, indent=2), encoding="utf-8")
