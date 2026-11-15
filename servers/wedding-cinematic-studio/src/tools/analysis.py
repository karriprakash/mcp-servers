"""Analysis tools: inspect reference video, photos and generated clips."""
from __future__ import annotations

import cv2
import numpy as np

from ..adapters import adapter_status as _adapter_status
from ..engines import face_qc, motion_qc


def adapter_status() -> dict:
    """Which video providers are usable right now, and why not if they are not."""
    return _adapter_status()


def analyze_reference_video(path: str) -> dict:
    """Duration, size, fps and the main action beats (motion-energy peaks) of a reference reel."""
    info = motion_qc.video_info(path)
    return {**info, "beats": motion_qc.find_beats(path)}


def inspect_photo(path: str) -> dict:
    """Check a couple photo is usable: size, sharpness, brightness and number of faces."""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {path}")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sharp = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    faces = face_qc.detect_faces(img)
    detector_ran = faces is not None
    notes = []
    if faces is None:
        notes.append("no face detector installed (pip install insightface onnxruntime): face check skipped")
        faces = []
    if min(h, w) < 600:
        notes.append("low resolution: use a photo at least 600px on the short side")
    if sharp < 60:
        notes.append("looks blurry")
    if detector_ran and len(faces) == 0:
        notes.append("no frontal face detected")
    return {
        "width": w, "height": h,
        "sharpness": round(sharp, 1),
        "brightness": round(float(np.mean(gray)), 1),
        "faces": [{"x": int(x), "y": int(y), "w": int(fw), "h": int(fh)} for x, y, fw, fh in faces],
        "usable": not [n for n in notes if "skipped" not in n],
        "notes": notes,
    }


def check_clip_quality(video_path: str, person_photos: dict[str, list[str]] | None = None, expected_faces: int | None = 2) -> dict:
    """Motion check (jumps, flicker, frozen) plus, when portraits are given, a face identity check."""
    out = {"motion": motion_qc.analyze_motion(video_path)}
    if person_photos:
        out["face"] = face_qc.check_identity(video_path, person_photos, expected_faces=expected_faces)
    return out


def register(mcp) -> None:
    for fn in (adapter_status, analyze_reference_video, inspect_photo, check_clip_quality):
        mcp.tool()(fn)
