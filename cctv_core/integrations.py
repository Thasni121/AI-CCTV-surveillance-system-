
"""
Optional integration helpers. Configure real URLs and credentials only after approval.
No external request is sent by default.
"""
import os
import requests

def send_webhook(payload, url_env="CCTV_ALERT_WEBHOOK_URL", timeout=5):
    url = os.environ.get(url_env, "").strip()
    if not url:
        return {"sent": False, "reason": f"{url_env} environment variable is not configured"}
    try:
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return {"sent": True, "status_code": response.status_code}
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}

def submit_face_crop(image_path, api_url, api_key_env="FR_API_KEY", timeout=10):
    """
    Placeholder adapter for an authorized FR service.
    Match the request/response schema to the official service specification.
    Do not upload biometric data without legal authority, notice, and security approval.
    """
    api_key = os.environ.get(api_key_env, "")
    if not api_url or not api_key:
        return {"submitted": False, "reason": "FR API URL/key not configured"}
    try:
        with open(image_path, "rb") as image_file:
            response = requests.post(api_url, headers={"Authorization": f"Bearer {api_key}"},
                                     files={"image": image_file}, timeout=timeout)
        response.raise_for_status()
        return {"submitted": True, "status_code": response.status_code, "response": response.text[:1000]}
    except Exception as exc:
        return {"submitted": False, "reason": str(exc)}

def run_plate_ocr(plate_crop_path):
    """
    OCR integration point. Install/configure EasyOCR or another approved OCR engine,
    then implement crop preprocessing and plate-specific validation for your camera/domain.
    """
    try:
        import easyocr
        import cv2
        reader = easyocr.Reader(["en"], gpu=False)
        image = cv2.imread(str(plate_crop_path))
        if image is None:
            return {"text": None, "reason": "Image could not be read"}
        candidates = reader.readtext(image, detail=0)
        return {"text": " ".join(candidates).strip() or None, "candidates": candidates}
    except Exception as exc:
        return {"text": None, "reason": str(exc)}
