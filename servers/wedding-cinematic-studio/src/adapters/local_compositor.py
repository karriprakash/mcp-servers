"""Local compositor: needs no API key and never distorts the card.

It draws the "scroll unrolls and reveals the wedding card" effect with your real card image:
a rod drops in on strings, the card is revealed top to bottom with a rolled-paper edge and a
soft shadow, then an optional confetti burst fires. The effect is drawn over either an AI clip
(base_video) or a procedural warm-maroon bokeh background when no clip is given.
"""
from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .base import SceneRequest, SceneResult, VideoAdapter

BRASS = (60, 150, 205)       # BGR
WOOD_D = (22, 38, 78)
WOOD_L = (60, 95, 150)
PAPER = (205, 228, 240)
CONFETTI = [(40, 190, 250), (60, 60, 200), (150, 80, 220), (30, 140, 245), (240, 240, 250), (90, 200, 120)]


def _ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _cover(frame: np.ndarray, w: int, h: int) -> np.ndarray:
    fh, fw = frame.shape[:2]
    s = max(w / fw, h / fh)
    r = cv2.resize(frame, (max(w, int(fw * s + 0.5)), max(h, int(fh * s + 0.5))), interpolation=cv2.INTER_AREA)
    y0, x0 = (r.shape[0] - h) // 2, (r.shape[1] - w) // 2
    return r[y0:y0 + h, x0:x0 + w]


class _Background:
    """Warm maroon gradient with slow golden bokeh, used when there is no base clip."""

    def __init__(self, w: int, h: int, seed: int = 7):
        self.w, self.h = w, h
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        top, bot = np.array([20, 8, 38], np.float32), np.array([8, 3, 18], np.float32)
        glow = np.exp(-((yy - 0.35) ** 2) / 0.08)
        grad = top * (1 - yy) + bot * yy + glow * np.array([25, 18, 55], np.float32) * 0.6
        self.base = np.repeat(grad[:, None, :], w, axis=1).astype(np.float32)
        rng = np.random.default_rng(seed)
        n = 34
        self.p = np.stack([rng.uniform(0, 1, n), rng.uniform(0, 1, n), rng.uniform(0.012, 0.05, n),
                           rng.uniform(0.01, 0.04, n), rng.uniform(0, 6.28, n), rng.uniform(0.25, 0.8, n)], 1)
        vy, vx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((vx - w / 2) / (w * 0.75)) ** 2 + ((vy - h / 2) / (h * 0.75)) ** 2)
        self.vig = np.clip(1.15 - d * 0.75, 0.35, 1.0)[..., None]

    def frame(self, t: float) -> np.ndarray:
        sw, sh = self.w // 4, self.h // 4
        layer = np.zeros((sh, sw, 3), np.float32)
        for x, y, r, sp, ph, a in self.p:
            cy = (y - sp * t) % 1.0
            cx = x + 0.015 * math.sin(t * 0.7 + ph)
            col = np.array([40, 140, 255], np.float32) * a * (0.6 + 0.4 * math.sin(t * 1.3 + ph))
            cv2.circle(layer, (int(cx * sw), int(cy * sh)), max(2, int(r * sw)), col.tolist(), -1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 2.2)
        layer = cv2.resize(layer, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        out = (self.base + layer * 0.55) * self.vig
        return np.clip(out, 0, 255).astype(np.uint8)


class _Confetti:
    def __init__(self, w: int, h: int, t0: float, n: int = 260, seed: int = 11):
        rng = np.random.default_rng(seed)
        self.w, self.h, self.t0 = w, h, t0
        side = rng.integers(0, 2, n)
        self.x0 = np.where(side == 0, 0.02, 0.98) * w
        self.y0 = np.full(n, 0.80 * h)
        ang = np.where(side == 0, rng.uniform(55, 80, n), rng.uniform(100, 125, n)) * math.pi / 180
        spd = rng.uniform(0.9, 1.7, n) * h * 0.62
        self.vx, self.vy = spd * np.cos(ang), -spd * np.sin(ang)
        self.spin = rng.uniform(-9, 9, n)
        self.size = rng.uniform(0.006, 0.014, n) * w
        self.col = rng.integers(0, len(CONFETTI), n)
        self.delay = rng.uniform(0, 0.25, n)
        self.g = h * 0.55

    def draw(self, frame: np.ndarray, t: float) -> None:
        if t < self.t0:
            return
        for i in range(len(self.x0)):
            u = t - self.t0 - self.delay[i]
            if u < 0:
                continue
            drag = math.exp(-0.9 * u)
            x = self.x0[i] + self.vx[i] * (1 - drag) / 0.9
            y = self.y0[i] + self.vy[i] * (1 - drag) / 0.9 + 0.5 * self.g * u * u
            if y > self.h + 40 or x < -40 or x > self.w + 40:
                continue
            a = self.spin[i] * u
            sx = self.size[i] * (0.3 + 0.7 * abs(math.cos(a * 1.3)))
            sy = self.size[i] * 0.55
            cv2.ellipse(frame, (int(x), int(y)), (max(1, int(sx)), max(1, int(sy))), math.degrees(a) % 360, 0, 360,
                        CONFETTI[self.col[i]], -1, cv2.LINE_AA)


def _cylinder(w: int, r: int, c_light, c_dark) -> np.ndarray:
    """A horizontal rod / rolled paper, w wide and 2r tall, shaded like a cylinder."""
    h = max(2, 2 * r)
    v = np.linspace(-1, 1, h, dtype=np.float32)
    k = np.clip(0.5 + 0.5 * np.cos((v + 0.35) * 1.15), 0, 1)[:, None, None]
    cl, cd = np.array(c_light, np.float32), np.array(c_dark, np.float32)
    return np.repeat(cd * (1 - k) + cl * k, w, axis=1).astype(np.uint8)


def render_card_reveal(
    card_png: str,
    out_mp4: str,
    base_video: str | None = None,
    size: tuple[int, int] = (1080, 1920),
    fps: int = 24,
    duration: float | None = None,
    reveal_start: float = 2.0,
    reveal_end: float = 5.0,
    card_width_frac: float = 0.80,
    card_center_y_frac: float = 0.47,
    confetti_at: float | None = None,
    progress_cb=None,
) -> str:
    W, H = size
    card = cv2.imread(card_png, cv2.IMREAD_COLOR)
    if card is None:
        raise FileNotFoundError(f"Cannot read card image: {card_png}")
    cw = int(W * card_width_frac)
    ch = int(card.shape[0] * cw / card.shape[1])
    card = cv2.resize(card, (cw, ch), interpolation=cv2.INTER_AREA)
    x0 = (W - cw) // 2
    y_top = int(H * card_center_y_frac - ch / 2)
    y_top = max(y_top, 150)
    rod_r = max(9, int(W * 0.011))
    rod_w = cw + 2 * int(W * 0.03)
    rod_x = (W - rod_w) // 2
    rod = _cylinder(rod_w, rod_r, WOOD_L, WOOD_D)
    pad = 60
    shadow = np.zeros((ch + 2 * pad, cw + 2 * pad), np.float32)
    shadow[pad + 14:pad + ch + 14, pad + 8:pad + cw + 8] = 1.0
    shadow = cv2.GaussianBlur(shadow, (0, 0), 16)

    cap = cv2.VideoCapture(base_video) if base_video else None
    base_fps = fps
    base_frames = 0
    if cap is not None and cap.isOpened():
        base_fps = cap.get(cv2.CAP_PROP_FPS) or fps
        base_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    else:
        cap = None
    if duration is None:
        duration = (base_frames / base_fps) if base_frames else max(reveal_end + 4.0, 10.0)
    n_frames = int(round(duration * fps))
    bg = None if cap is not None else _Background(W, H)
    conf = _Confetti(W, H, confetti_at) if confetti_at is not None else None

    out = Path(out_mp4)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    has_audio = False
    if base_video:
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", base_video],
                               capture_output=True, text=True)
        has_audio = bool(probe.stdout.strip())
    if has_audio:
        cmd += ["-i", base_video, "-map", "0:v", "-map", "1:a:0", "-c:a", "aac", "-b:a", "160k", "-shortest"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(tmp)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    last = None
    try:
        for i in range(n_frames):
            t = i / fps
            if cap is not None:
                want = int(t * base_fps)
                # read forward to the wanted base frame, hold the last frame when the clip ends
                while cap.get(cv2.CAP_PROP_POS_FRAMES) <= want:
                    ok, f = cap.read()
                    if not ok:
                        break
                    last = f
                frame = _cover(last, W, H).copy() if last is not None else np.zeros((H, W, 3), np.uint8)
            else:
                frame = bg.frame(t)

            drop = _ease((t - (reveal_start - 1.0)) / 0.9)
            if drop > 0:
                p = _ease((t - reveal_start) / max(0.1, reveal_end - reveal_start))
                sway = (3.0 * math.sin((t - reveal_end) * 1.6) * math.exp(-(t - reveal_end) * 0.35)) if t > reveal_end else 0.0
                dx = int(sway)
                rod_y = int((-3 * rod_r) * (1 - drop) + (y_top - 2 * rod_r) * drop)
                # strings
                for sx in (x0 + int(cw * 0.16), x0 + int(cw * 0.84)):
                    cv2.line(frame, (sx + dx, 0), (sx + dx, rod_y + rod_r), BRASS, 2, cv2.LINE_AA)
                rev_h = int(ch * p)
                if rev_h > 0:
                    y1 = y_top + rev_h
                    ys0, ys1 = y_top, min(H, y_top + rev_h + pad)
                    xs0, xs1 = max(0, x0 - pad + dx), min(W, x0 - pad + dx + cw + 2 * pad)
                    sm = shadow[pad:pad + (ys1 - ys0), (xs0 - (x0 - pad + dx)):(xs0 - (x0 - pad + dx)) + (xs1 - xs0)]
                    roi = frame[ys0:ys1, xs0:xs1].astype(np.float32)
                    roi *= (1 - 0.5 * sm)[..., None]
                    frame[ys0:ys1, xs0:xs1] = roi.astype(np.uint8)
                    frame[y_top:y1, x0 + dx:x0 + dx + cw] = card[:rev_h]
                # bottom roll: rolled paper while unrolling, becomes a wooden rod when fully open
                r2 = int(rod_r * (1.9 - 0.9 * p))
                roll_w = cw + int(W * 0.012) + int(W * 0.02) * p
                roll = _cylinder(int(roll_w), r2, PAPER if p < 0.97 else WOOD_L, (120, 150, 175) if p < 0.97 else WOOD_D)
                ry = y_top + rev_h - r2 // 2 if rev_h > 0 else y_top - r2
                rx = int((W - roll.shape[1]) / 2) + dx
                if 0 <= ry and ry + roll.shape[0] < H and rx >= 0 and rx + roll.shape[1] <= W:
                    frame[ry:ry + roll.shape[0], rx:rx + roll.shape[1]] = roll
                    if p >= 0.97:
                        for ex in (rx, rx + roll.shape[1]):
                            cv2.circle(frame, (ex, ry + roll.shape[0] // 2), int(r2 * 1.05), BRASS, -1, cv2.LINE_AA)
                # top rod last so it sits on the card
                if 0 <= rod_y and rod_y + rod.shape[0] < H and rod_x + dx >= 0 and rod_x + dx + rod.shape[1] <= W:
                    frame[rod_y:rod_y + rod.shape[0], rod_x + dx:rod_x + dx + rod.shape[1]] = rod
                    for ex in (rod_x + dx, rod_x + dx + rod.shape[1]):
                        cv2.circle(frame, (ex, rod_y + rod_r), int(rod_r * 1.25), BRASS, -1, cv2.LINE_AA)
            if conf is not None:
                conf.draw(frame, t)
            proc.stdin.write(frame.tobytes())
            if progress_cb and i % 24 == 0:
                progress_cb(i / n_frames)
        proc.stdin.close()
        rc = proc.wait()
    except BrokenPipeError:
        rc = proc.wait()
    finally:
        if cap is not None:
            cap.release()
    if rc != 0:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"ffmpeg exited with code {rc}")
    os.replace(tmp, out)
    return str(out)


class LocalCompositorAdapter(VideoAdapter):
    """Scene kind 'card_reveal'. Needs extra['card_png']; optional extra['base_video']."""

    name = "local"

    def is_available(self) -> tuple[bool, str]:
        for tool in ("ffmpeg", "ffprobe"):
            if subprocess.run(["which", tool], capture_output=True).returncode != 0:
                return False, f"{tool} not found on PATH"
        return True, "ok"

    def generate(self, req: SceneRequest) -> SceneResult:
        card = req.extra.get("card_png")
        if not card or not Path(card).exists():
            return SceneResult(False, adapter=self.name, error="extra['card_png'] is missing or not a file")
        w, h = (1080, 1920) if req.aspect_ratio == "9:16" else (1920, 1080)
        try:
            path = render_card_reveal(
                card_png=card,
                out_mp4=req.out_path,
                base_video=req.extra.get("base_video"),
                size=(w, h),
                duration=req.duration or None,
                reveal_start=float(req.extra.get("reveal_start", 2.0)),
                reveal_end=float(req.extra.get("reveal_end", 5.0)),
                confetti_at=req.extra.get("confetti_at"),
            )
        except Exception as e:
            return SceneResult(False, adapter=self.name, error=f"{type(e).__name__}: {e}")
        return SceneResult(True, path, self.name)
