"""Motion quality control: finds jump cuts, flicker and frozen clips using dense optical flow."""
from __future__ import annotations

import cv2
import numpy as np


def _open(path: str):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {path}")
    return cap


def video_info(path: str) -> dict:
    cap = _open(path)
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": float(cap.get(cv2.CAP_PROP_FPS) or 0),
        "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
    }
    cap.release()
    info["duration"] = round(info["frames"] / info["fps"], 3) if info["fps"] else 0.0
    return info


def motion_curve(path: str, step: int = 1, small: int = 160) -> tuple[np.ndarray, np.ndarray, float]:
    """Return (mean flow magnitude per frame pair, mean luma per frame, fps)."""
    cap = _open(path)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 24)
    prev = None
    mags, luma = [], []
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step == 0:
            h, w = f.shape[:2]
            g = cv2.cvtColor(cv2.resize(f, (small, max(2, int(h * small / w)))), cv2.COLOR_BGR2GRAY)
            luma.append(float(g.mean()))
            if prev is not None:
                flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 2, 15, 2, 5, 1.1, 0)
                mags.append(float(np.linalg.norm(flow, axis=2).mean()))
            prev = g
        i += 1
    cap.release()
    return np.array(mags), np.array(luma), fps / step


def analyze_motion(path: str, min_duration: float = 1.0, max_jump_sigma: float = 6.0) -> dict:
    info = video_info(path)
    mags, luma, eff_fps = motion_curve(path)
    flags: list[str] = []
    jump_frames: list[int] = []
    if len(mags) < 3:
        return {**info, "passed": False, "flags": ["too few frames to analyse"], "jump_frames": []}

    mu, sd = float(mags.mean()), float(mags.std())
    thresh = mu + max_jump_sigma * max(sd, 0.05)
    jump_frames = [int(i) for i in np.where((mags > thresh) & (mags > 3.0))[0]]
    if jump_frames:
        flags.append(f"{len(jump_frames)} sudden jump(s) near frames {jump_frames[:5]}")

    flicker = np.abs(np.diff(luma))
    flicker_n = int((flicker > 12).sum())
    if flicker_n > 2:
        flags.append(f"{flicker_n} brightness flickers")

    if mu < 0.03:
        flags.append("clip is nearly frozen (no motion)")
    if info["duration"] < min_duration:
        flags.append(f"clip is only {info['duration']}s long")

    return {
        **info,
        "mean_motion": round(mu, 4),
        "peak_motion": round(float(mags.max()), 4),
        "jump_frames": jump_frames,
        "flicker_count": flicker_n,
        "flags": flags,
        "passed": not flags,
    }


def find_beats(path: str, min_gap: float = 0.8, top_k: int = 12) -> list[dict]:
    """Rough action beats of a reference video: times where motion energy peaks."""
    mags, _, fps = motion_curve(path)
    if len(mags) < 5:
        return []
    k = max(1, int(fps * 0.25))
    sm = np.convolve(mags, np.ones(k) / k, mode="same")
    order = np.argsort(sm)[::-1]
    beats: list[dict] = []
    for idx in order:
        t = idx / fps
        if all(abs(t - b["time"]) >= min_gap for b in beats):
            beats.append({"time": round(float(t), 2), "energy": round(float(sm[idx]), 3)})
        if len(beats) >= top_k:
            break
    return sorted(beats, key=lambda b: b["time"])
