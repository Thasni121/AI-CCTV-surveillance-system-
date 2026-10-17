
# AI CCTV Surveillance System — Full Starter Project

A local Python/Flask prototype for CCTV video upload, YOLO object detection, ByteTrack tracking, annotated video output, event logs, evidence snapshots and a dashboard.

## Included modules
- Upload recorded video in common formats.
- YOLO object detection for COCO classes including person, car, motorcycle, bus and truck.
- ByteTrack tracking IDs where supported by the model/tracker.
- Annotated MP4 output.
- Configurable confidence threshold and frame stride.
- Optional CLAHE low-light enhancement.
- Evidence crop snapshots with a cooldown.
- Basic event records for detections, line crossing and crowd threshold.
- Dashboard, event list, processing summary and settings page.
- OCR integration helper (`cctv_core/integrations.py`) using optional EasyOCR.
- Authorized Face Recognition API adapter placeholder and webhook adapter.
- RTSP configuration placeholder for future live multi-camera implementation.

## Important limits — read before using
This is a **starter prototype**, not a complete production/mission-critical surveillance system.
- Vehicle detection uses general YOLO classes; it does not train a highway-specific model.
- Number plate detection/cropping is not implemented end-to-end. OCR helper only reads a supplied plate crop; a dedicated plate detector is still required.
- Face detection/recognition pipeline and Delhi Police FR service contract are not configured. The adapter is a template; obtain the official API schema and authorization.
- No live RTSP camera processing or robust multi-camera orchestration is implemented.
- Alerts are logged locally; webhook helper is not automatically called from the video processor.
- “Crowd threshold” is a simple count of detected people in one processed frame, not a calibrated crowd-density estimate.
- Line crossing uses tracked box-centres and a horizontal line; it needs camera-specific tuning and review.
- False positives, occlusion, low light, motion blur and camera-angle errors need validation against representative footage.
- Per-frame detection sums are not unique vehicle/person counts. Tracking IDs can change.
- There is no login, role-based access, TLS, audit-grade tamper-proof storage or retention scheduler. Run locally on a trusted machine only.
- Do not use face recognition or share biometric imagery without legal authority, privacy review, access controls and an approved data-handling policy.

## Requirements
- Windows 10/11 or Linux.
- Python 3.11 recommended.
- Internet access on first setup to install packages and download YOLO model weights.
- For longer videos, a capable CPU/GPU and sufficient disk space are recommended.

## Run on Windows
1. Extract the ZIP to a writable folder.
2. Install Python 3.11 and make sure the Python launcher (`py`) works.
3. Double-click `run_windows.bat`, or open a terminal in this folder and run:

   ```powershell
   py -3.11 -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python app.py
   ```

4. Open `http://127.0.0.1:5000` in your browser.
5. Upload a short MP4 first and check the output/evidence folders.

If `py -3.11` does not work, install Python 3.11 or edit the batch file to use your installed Python executable.

## Settings
- `confidence`: higher values often reduce false positives but can miss objects.
- `frame_stride`: 1 processes every frame; 2 processes every second frame, etc. Skipped frames are copied into output without detection.
- `snapshot_interval_sec`: minimum time between snapshots for a track/class.
- `enable_low_light`: applies CLAHE to the luminance channel. Test whether this helps your specific camera.
- `crowd_threshold`: number of person detections in a single processed frame to emit a crowd event.
- `zone_line_y_ratio`: horizontal line vertical position as a fraction of image height.

## Integrations
- `cctv_core/integrations.py` has optional functions for webhook delivery, OCR on an already-cropped plate, and an authorized FR API adapter.
- Do not invent API endpoints. Use the official service contract and test against a sandbox.
- Set secrets as environment variables; do not put keys into `config.json` or commit them to GitHub.
- The application does not upload footage or face crops to external services by default.

## Project layout
```text
AI_CCTV_Surveillance_System_Full/
  app.py
  config.json
  cctv_core/
    config.py
    events.py
    integrations.py
    processor.py
  templates/
  static/
  uploads/
  outputs/
  evidence/
  data/
```

## Next production steps
1. Validate against representative highway CCTV clips and annotate false positives/false negatives.
2. Implement a dedicated number-plate detector and region-specific OCR post-processing.
3. Integrate only the official, authorized FR API; add consent/legal basis, encryption, retention and access auditing.
4. Implement real RTSP ingest, per-camera queues, reconnection and GPU batching.
5. Add authenticated users, role permissions, secure secret management, monitoring and automated cleanup.
6. Build a proper alert dispatcher with retries and rate limits, then test it with a non-production endpoint.
7. Measure latency, throughput, accuracy and disk/network bandwidth before deployment.


## Merged output/evidence behaviour

This merged version retains the settings/events dashboard and adds the original-style results to each job page:
- Browser-playable H.264 MP4 is created with FFmpeg when FFmpeg is installed and available on PATH. If conversion fails, the original OpenCV MP4 is retained and a message is printed in the terminal.
- The job page embeds the annotated video player and offers a download link.
- Evidence gallery shows object crops and periodic full-frame annotated snapshots for the processed job.
- Evidence and output routes serve files inline so images/video can be previewed in the browser.

Run on Windows:
1. Extract the ZIP.
2. Open the extracted project folder in VS Code.
3. Open Terminal in that folder.
4. Run `py -3.11 -m venv .venv`
5. Run `.\.venv\Scripts\Activate.ps1`
6. Run `python -m pip install --upgrade pip`
7. Run `pip install -r requirements.txt`
8. Run `python app.py`
9. Open `http://127.0.0.1:5000`

FFmpeg is optional but recommended for browser playback. Install it and ensure `ffmpeg -version` works in the same VS Code terminal. Live multi-camera RTSP ingestion and actual face-recognition/number-plate recognition require separate integration/configuration and are not claimed to be fully implemented by this prototype.


## Intelligent alert engine (added)

The upload-processing prototype now includes rule-based alerts:
- **Restricted-zone intrusion (CRITICAL):** an object's tracked centre enters a configured rectangular zone. Zone ratios are editable in Settings; defaults are a sample zone and must be adjusted to your camera view.
- **Loitering (HIGH):** a person track remains visible long enough to pass the configured threshold. Tracking can reset under occlusion, so this is an estimate.
- **Line crossing (MEDIUM):** tracked object centre crosses the configured horizontal line.
- **Crowd threshold (HIGH):** the number of detected people in a frame reaches the configured threshold.
- **Ordinary detections (LOW)** remain in the event log.
- The Events page shows severity and event type. The browser can beep for new HIGH/CRITICAL events while the page is open; click **Enable sound alerts** once.
- Optional email/SMS delivery is attempted only for HIGH/CRITICAL events, only when enabled in Settings, and only when provider environment variables are configured.

### Email environment variables (do not commit secrets)
`CCTV_SMTP_HOST`, `CCTV_SMTP_PORT` (usually 587), `CCTV_SMTP_USER`, `CCTV_SMTP_PASSWORD`, `CCTV_ALERT_EMAIL_TO`; optional `CCTV_ALERT_EMAIL_FROM`.

### SMS via Twilio
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `CCTV_ALERT_SMS_TO`. Twilio account, verified/authorized numbers, billing and service availability are required.

On Windows PowerShell, set variables for the current terminal before starting the app, for example:
```powershell
$env:CCTV_SMTP_HOST="smtp.example.com"
$env:CCTV_SMTP_PORT="587"
$env:CCTV_SMTP_USER="your-account@example.com"
$env:CCTV_SMTP_PASSWORD="your-app-password"
$env:CCTV_ALERT_EMAIL_TO="recipient@example.com"
python app.py
```
Use real provider details; the values above are examples only. Do not place passwords in `config.json` or source files.

**Limitations:** this is a rule-based prototype, not a semantic AI system that understands intent. Zone geometry is a rectangle in normalized coordinates, line crossing is horizontal, and loitering relies on tracker IDs. Test/adjust thresholds on representative footage and have a person verify alerts before operational use. Continuous RTSP monitoring and guaranteed delivery/retry queues are not implemented. Email/SMS cannot send until correctly configured.
