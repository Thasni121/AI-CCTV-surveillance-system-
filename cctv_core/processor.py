
import os, time, json, shutil, subprocess
from pathlib import Path
from datetime import datetime
import cv2
from .events import write_event
from .alert_engine import emit_alert

VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck"}
PERSON_CLASS = "person"

def enhance_low_light(frame):
    # Optional CLAHE enhancement. Useful for some dark footage, but not a substitute for IR/lighting.
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return cv2.cvtColor(cv2.merge((clahe.apply(l), a, b)), cv2.COLOR_LAB2BGR)

def process_video(video_path, root, settings, job_id):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Ultralytics is missing. Install dependencies with run_windows.bat or pip install -r requirements.txt.") from exc

    root = Path(root)
    model = YOLO(settings.get("model_name", "yolo11n.pt"))
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("OpenCV could not open this video. Try a standard MP4/H.264 file.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 480)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    output_path = root / "outputs" / f"{job_id}_annotated.mp4"
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("Could not create output video. Check write permissions and codec support.")

    events_path = root / "data" / "events.jsonl"
    stride = max(1, int(settings.get("frame_stride", 1)))
    confidence = float(settings.get("confidence", 0.35))
    snapshot_gap = max(0.5, float(settings.get("snapshot_interval_sec", 2)))
    cooldown = max(1, int(settings.get("event_cooldown_sec", 5)))
    allowed = set(settings.get("classes", []))
    last_snapshot = {}
    last_annotated_snapshot = -999.0
    last_event = {}
    seen_track_ids = set()
    class_frame_counts = {}
    frame_idx = 0
    processed = 0
    event_count = 0
    vehicle_count = 0
    person_count = 0
    crossed_ids = set()
    line_y = int(height * float(settings.get("zone_line_y_ratio", 0.65)))
    crowd_threshold = int(settings.get("crowd_threshold", 8))
    line_prev = {}
    last_crowd_alert = -999999.0
    track_first_seen = {}
    loitered_ids = set()
    zone_intrusion_ids = set()
    zone_enabled = bool(settings.get("restricted_zone_enabled", True))
    zx1 = int(width * float(settings.get("zone_x1_ratio", 0.35)))
    zy1 = int(height * float(settings.get("zone_y1_ratio", 0.30)))
    zx2 = int(width * float(settings.get("zone_x2_ratio", 0.85)))
    zy2 = int(height * float(settings.get("zone_y2_ratio", 0.85)))
    loiter_threshold = max(1, float(settings.get("loitering_threshold_sec", 15)))

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_idx += 1
            if settings.get("enable_low_light", False):
                frame = enhance_low_light(frame)
            if (frame_idx - 1) % stride != 0:
                writer.write(frame)
                continue

            results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=confidence,
                                  iou=float(settings.get("iou", 0.45)), verbose=False)
            result = results[0]
            annotated = result.plot()
            processed += 1
            boxes = result.boxes
            people_this_frame = 0
            if boxes is not None:
                for i, box in enumerate(boxes):
                    cls_id = int(box.cls[0].item())
                    class_name = model.names.get(cls_id, str(cls_id))
                    conf = float(box.conf[0].item()) if box.conf is not None else 0.0
                    if allowed and class_name not in allowed:
                        continue
                    class_frame_counts[class_name] = class_frame_counts.get(class_name, 0) + 1
                    xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
                    x1, y1, x2, y2 = xyxy
                    track_id = None
                    if boxes.id is not None and i < len(boxes.id):
                        track_id = int(boxes.id[i].item())
                        seen_track_ids.add(track_id)
                    if class_name in VEHICLE_CLASSES:
                        vehicle_count += 1
                    if class_name == PERSON_CLASS:
                        people_this_frame += 1
                        person_count += 1
                    now = frame_idx / max(fps, 1)
                    # Save evidence snapshots with cooldown per track/class.
                    snap_key = str(track_id) if track_id is not None else class_name
                    crop = frame[max(0,y1):max(0,y2), max(0,x1):max(0,x2)]
                    snap_name = None
                    if now - last_snapshot.get(snap_key, -999) >= snapshot_gap:
                        if crop.size:
                            snap_name = f"{job_id}_f{frame_idx}_{class_name}_{track_id if track_id is not None else 'na'}.jpg"
                            cv2.imwrite(str(root / "evidence" / snap_name), crop)
                            last_snapshot[snap_key] = now
                    # Event types: detection, vehicle, zone-line crossing, crowd threshold.
                    event_key = f"{class_name}:{track_id if track_id is not None else 'na'}"
                    if now - last_event.get(event_key, -999) >= cooldown:
                        event_type = "vehicle_detected" if class_name in VEHICLE_CLASSES else "person_detected" if class_name == PERSON_CLASS else "object_detected"
                        event = {"timestamp": datetime.now().isoformat(timespec="seconds"), "job_id": job_id,
                                 "video": settings.get("video_name", Path(video_path).name), "frame": frame_idx,
                                 "video_time_sec": round(now, 2), "event_type": event_type,
                                 "class_name": class_name, "confidence": round(conf, 3), "track_id": track_id,
                                 "bbox_xyxy": xyxy, "evidence": snap_name if crop.size else None}
                        emit_alert(events_path, event, settings)
                        event_count += 1
                        last_event[event_key] = now
                    # Approximate line crossing using tracked centre. Configure line in settings.
                    if track_id is not None:
                        center_y = int((y1 + y2) / 2)
                        center_x = int((x1 + x2) / 2)
                        track_first_seen.setdefault(track_id, now)
                        # Restricted-zone intrusion: object centre enters the configured rectangle.
                        inside_zone = zone_enabled and zx1 <= center_x <= zx2 and zy1 <= center_y <= zy2
                        if inside_zone and track_id not in zone_intrusion_ids:
                            zone_intrusion_ids.add(track_id)
                            emit_alert(events_path, {
                                "timestamp": datetime.now().isoformat(timespec="seconds"), "job_id": job_id,
                                "video": settings.get("video_name", Path(video_path).name), "frame": frame_idx,
                                "video_time_sec": round(now, 2), "event_type": "restricted_zone_intrusion",
                                "class_name": class_name, "confidence": round(conf, 3), "track_id": track_id,
                                "bbox_xyxy": xyxy, "evidence": snap_name,
                                "zone_xyxy": [zx1, zy1, zx2, zy2]
                            }, settings)
                            event_count += 1
                        # Loitering rule applies to person tracks only; first trigger per track.
                        if class_name == PERSON_CLASS and track_id not in loitered_ids:
                            dwell = now - track_first_seen[track_id]
                            if dwell >= loiter_threshold:
                                loitered_ids.add(track_id)
                                emit_alert(events_path, {
                                    "timestamp": datetime.now().isoformat(timespec="seconds"), "job_id": job_id,
                                    "video": settings.get("video_name", Path(video_path).name), "frame": frame_idx,
                                    "video_time_sec": round(now, 2), "event_type": "loitering",
                                    "class_name": class_name, "confidence": round(conf, 3), "track_id": track_id,
                                    "bbox_xyxy": xyxy, "dwell_time_sec": round(dwell, 2), "evidence": snap_name
                                }, settings)
                                event_count += 1
                        prev_y = line_prev.get(track_id)
                        if prev_y is not None and ((prev_y < line_y <= center_y) or (prev_y > line_y >= center_y)):
                            if track_id not in crossed_ids:
                                crossed_ids.add(track_id)
                                event = {"timestamp": datetime.now().isoformat(timespec="seconds"), "job_id": job_id,
                                         "video": settings.get("video_name", Path(video_path).name), "frame": frame_idx,
                                         "video_time_sec": round(now, 2), "event_type": "line_crossing",
                                         "class_name": class_name, "confidence": round(conf, 3), "track_id": track_id,
                                         "bbox_xyxy": xyxy, "line_y": line_y}
                                emit_alert(events_path, event, settings)
                                event_count += 1
                        line_prev[track_id] = center_y

            cv2.line(annotated, (0, line_y), (width, line_y), (0, 255, 255), 2)
            if zone_enabled:
                cv2.rectangle(annotated, (zx1, zy1), (zx2, zy2), (0, 0, 255), 2)
                cv2.putText(annotated, "RESTRICTED ZONE", (zx1, max(20, zy1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(annotated, f"Frame {frame_idx}/{total or '?'} | Tracks: {len(seen_track_ids)}",
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            # Preserve the original project's full-frame annotated evidence snapshots.
            current_video_time = frame_idx / max(fps, 1)
            if boxes is not None and len(boxes) > 0 and current_video_time - last_annotated_snapshot >= snapshot_gap:
                snapshot_name = f"{job_id}_snapshot_f{frame_idx:06d}.jpg"
                cv2.imwrite(str(root / "evidence" / snapshot_name), annotated)
                last_annotated_snapshot = current_video_time
            if people_this_frame >= crowd_threshold and (frame_idx / max(fps, 1) - last_crowd_alert) >= cooldown:
                emit_alert(events_path, {"timestamp": datetime.now().isoformat(timespec="seconds"), "job_id": job_id,
                             "video": settings.get("video_name", Path(video_path).name), "frame": frame_idx,
                             "video_time_sec": round(frame_idx / max(fps, 1), 2), "event_type": "crowd_threshold",
                             "people_in_frame": people_this_frame, "threshold": crowd_threshold}, settings)
                event_count += 1
                last_crowd_alert = frame_idx / max(fps, 1)
            writer.write(annotated)
    finally:
        cap.release()
        writer.release()

    # Convert OpenCV mp4v output to H.264 so browsers can play it.
    browser_path = root / "outputs" / f"{job_id}_browser.mp4"
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        conversion = subprocess.run(
            [ffmpeg, "-y", "-i", str(output_path), "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(browser_path)],
            capture_output=True, text=True
        )
        if conversion.returncode == 0 and browser_path.exists() and browser_path.stat().st_size > 0:
            output_path = browser_path
        else:
            # Keep the OpenCV output available if conversion fails.
            print("FFmpeg conversion failed:", conversion.stderr[-1000:])
    else:
        print("FFmpeg was not found; browser playback may depend on the installed codec.")

    evidence_files = sorted(
        [f.name for f in (root / "evidence").glob(f"{job_id}_*.jpg")],
        reverse=True
    )
    summary = {"job_id": job_id, "input": settings.get("video_name", Path(video_path).name),
               "output": output_path.name, "evidence_files": evidence_files,
               "fps": round(fps, 2), "width": width, "height": height,
               "total_frames": total, "processed_frames": processed, "frame_stride": stride,
               "approx_unique_track_ids": len(seen_track_ids), "vehicle_detections_per_frame_sum": vehicle_count,
               "person_detections_per_frame_sum": person_count, "events_written_estimate": event_count,
               "class_detections_per_frame_sum": class_frame_counts,
               "note": "Counts labelled per-frame are not unique vehicle/person counts. Track IDs can change under occlusion."}
    (root / "data" / f"{job_id}_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
