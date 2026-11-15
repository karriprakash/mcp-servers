"""Face identity QC.

With `insightface` installed this uses ArcFace embeddings (reliable). Without it, it falls back
to OpenCV face detection plus a colour-histogram comparison, which can catch "wrong number of
faces" and gross skin/colour drift but cannot truly verify identity. The result says which
backend ran in `backend` and `reliable`.
"""
from __future__ import annotations

import cv2
import numpy as np

_insight_app = None


def _load_insight():
    global _insight_app
    if _insight_app is None:
        from insightface.app import FaceAnalysis  # type: ignore

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _insight_app = app
    return _insight_app


def _haar_path() -> str | None:
    import os

    base = getattr(getattr(cv2, "data", None), "haarcascades", None)
    if base:
        p = os.path.join(base, "haarcascade_frontalface_default.xml")
        if os.path.exists(p):
            return p
    return None


def _backend() -> str:
    """insightface (reliable) > OpenCV Haar (weak) > none."""
    try:
        import insightface  # noqa: F401

        return "insightface"
    except Exception:
        return "opencv-fallback" if _haar_path() else "none"


def detect_faces(img: np.ndarray) -> list[tuple[int, int, int, int]] | None:
    """Face boxes (x, y, w, h), or None when no detector is installed in this environment."""
    be = _backend()
    if be == "insightface":
        return [(int(f.bbox[0]), int(f.bbox[1]), int(f.bbox[2] - f.bbox[0]), int(f.bbox[3] - f.bbox[1]))
                for f in _load_insight().get(img)]
    if be == "opencv-fallback":
        return _haar_faces(img)
    return None


_haar = None


def _haar_faces(img: np.ndarray) -> list[tuple[int, int, int, int]]:
    global _haar
    if _haar is None:
        _haar = cv2.CascadeClassifier(_haar_path())
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _haar.detectMultiScale(g, 1.1, 5, minSize=(max(30, img.shape[1] // 25),) * 2)
    return [tuple(int(v) for v in f) for f in faces]


def _hist(img: np.ndarray, box) -> np.ndarray:
    x, y, w, h = box
    crop = img[y:y + h, x:x + w]
    # centre of the face only: less background and hair
    ch, cw = crop.shape[:2]
    crop = crop[int(ch * .2):int(ch * .85), int(cw * .15):int(cw * .85)]
    hsv = cv2.cvtColor(cv2.resize(crop, (64, 64)), cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
    return cv2.normalize(hist, hist).flatten()


def _embed_all(img: np.ndarray, backend: str) -> list[np.ndarray]:
    if backend == "insightface":
        faces = _load_insight().get(img)
        faces = sorted(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
        return [f.normed_embedding for f in faces]
    return [_hist(img, b) for b in _haar_faces(img)]


def _sim(a: np.ndarray, b: np.ndarray, backend: str) -> float:
    if backend == "insightface":
        return float(np.dot(a, b))
    return float(cv2.compareHist(a.astype(np.float32), b.astype(np.float32), cv2.HISTCMP_CORREL))


def check_identity(
    video_path: str,
    references: dict[str, list[str]],
    sample_every: int = 12,
    threshold: float | None = None,
    expected_faces: int | None = None,
) -> dict:
    """references: {"groom": ["groom_portrait.jpg"], "bride": ["bride_portrait.jpg"]}.

    Each reference image should show one person (the biggest face is used)."""
    backend = _backend()
    if backend == "none":
        return {
            "backend": "none", "reliable": False, "skipped": True, "passed": True, "per_person": {},
            "flags": ["no face detector available: install insightface + onnxruntime to enable the identity check"],
        }
    if threshold is None:
        threshold = 0.30 if backend == "insightface" else 0.45

    ref_emb: dict[str, list[np.ndarray]] = {}
    for person, paths in references.items():
        for p in paths:
            img = cv2.imread(p)
            if img is None:
                continue
            embs = _embed_all(img, backend)
            if embs:
                ref_emb.setdefault(person, []).append(embs[0])
    missing = [p for p in references if p not in ref_emb]

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    best: dict[str, list[float]] = {p: [] for p in ref_emb}
    counts: list[int] = []
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % sample_every == 0:
            embs = _embed_all(f, backend)
            counts.append(len(embs))
            for person, refs in ref_emb.items():
                scores = [_sim(e, r, backend) for e in embs for r in refs]
                if scores:
                    best[person].append(max(scores))
        i += 1
    cap.release()

    per_person = {}
    flags: list[str] = []
    for person in references:
        vals = best.get(person, [])
        if not vals:
            per_person[person] = {"frames_matched": 0, "mean": None, "best": None}
            flags.append(f"{person}: no face found in any sampled frame" if person in ref_emb
                         else f"{person}: no face found in the reference image")
            continue
        m = float(np.mean(vals))
        per_person[person] = {"frames_matched": len(vals), "mean": round(m, 3), "best": round(float(max(vals)), 3)}
        if m < threshold:
            flags.append(f"{person}: mean similarity {m:.2f} is below {threshold:.2f}")
    if expected_faces is not None and counts:
        off = sum(1 for c in counts if c != expected_faces)
        if off > len(counts) * 0.4:
            flags.append(f"face count differs from {expected_faces} in {off}/{len(counts)} sampled frames")

    return {
        "backend": backend,
        "reliable": backend == "insightface",
        "threshold": threshold,
        "per_person": per_person,
        "missing_references": missing,
        "mean_faces_per_frame": round(float(np.mean(counts)), 2) if counts else 0.0,
        "flags": flags,
        "passed": not flags,
    }
