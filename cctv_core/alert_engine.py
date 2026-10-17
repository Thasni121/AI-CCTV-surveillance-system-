"""Rule-based alert severity and optional email/SMS notification helpers."""
import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
import requests

SEVERITY = {
    "restricted_zone_intrusion": "CRITICAL",
    "loitering": "HIGH",
    "crowd_threshold": "HIGH",
    "line_crossing": "MEDIUM",
    "person_detected": "LOW",
    "vehicle_detected": "LOW",
    "object_detected": "LOW",
}

def enrich_alert(event):
    event = dict(event)
    event_type = event.get("event_type", "object_detected")
    event["severity"] = SEVERITY.get(event_type, "LOW")
    event["alert_title"] = {
        "restricted_zone_intrusion": "Restricted-zone intrusion",
        "loitering": "Loitering threshold reached",
        "crowd_threshold": "Crowd threshold reached",
        "line_crossing": "Line crossing detected",
    }.get(event_type, event_type.replace("_", " ").title())
    event["alert_id"] = event.get("alert_id") or (
        f"{event.get('job_id','job')}-{event.get('frame','0')}-{event_type}-{event.get('track_id','na')}"
    )
    return event

def notify_email(event):
    host = os.getenv("CCTV_SMTP_HOST", "").strip()
    user = os.getenv("CCTV_SMTP_USER", "").strip()
    password = os.getenv("CCTV_SMTP_PASSWORD", "")
    to_addr = os.getenv("CCTV_ALERT_EMAIL_TO", "").strip()
    if not all([host, user, password, to_addr]):
        return {"sent": False, "reason": "SMTP/email environment variables are not configured"}
    msg = EmailMessage()
    msg["Subject"] = f"[CCTV {event.get('severity')}] {event.get('alert_title')}"
    msg["From"] = os.getenv("CCTV_ALERT_EMAIL_FROM", user)
    msg["To"] = to_addr
    msg.set_content(
        f"Alert: {event.get('alert_title')}\nSeverity: {event.get('severity')}\n"
        f"Event type: {event.get('event_type')}\nCamera/video: {event.get('video')}\n"
        f"Timestamp: {event.get('timestamp')}\nVideo time: {event.get('video_time_sec')} sec\n"
        f"Class: {event.get('class_name')}\nTrack ID: {event.get('track_id')}\n"
        f"Confidence: {event.get('confidence')}\nEvidence: {event.get('evidence')}\n"
        "Please review the evidence; automated detections can be incorrect."
    )
    try:
        port = int(os.getenv("CCTV_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return {"sent": True}
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}

def notify_sms(event):
    sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_num = os.getenv("TWILIO_FROM_NUMBER", "").strip()
    to_num = os.getenv("CCTV_ALERT_SMS_TO", "").strip()
    if not all([sid, token, from_num, to_num]):
        return {"sent": False, "reason": "Twilio SMS environment variables are not configured"}
    text = (f"[CCTV {event.get('severity')}] {event.get('alert_title')}; "
            f"{event.get('video')} at {event.get('video_time_sec')}s. Review dashboard.")
    try:
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"From": from_num, "To": to_num, "Body": text},
            auth=(sid, token), timeout=10
        )
        response.raise_for_status()
        return {"sent": True, "status_code": response.status_code}
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}

def emit_alert(path, event, settings=None):
    """Persist enriched event and send configured notifications for HIGH/CRITICAL events."""
    from .events import write_event
    event = enrich_alert(event)
    settings = settings or {}
    should_notify = event["severity"] in {"HIGH", "CRITICAL"}
    if should_notify:
        if settings.get("enable_email_alerts", False):
            event["email_notification"] = notify_email(event)
        if settings.get("enable_sms_alerts", False):
            event["sms_notification"] = notify_sms(event)
    write_event(path, event)
    return event
