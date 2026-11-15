"""Assembly tools: card compositing, normalising and stitching scenes, music, thumbnail."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .. import config
from ..adapters.local_compositor import render_card_reveal
from ..engines.motion_qc import video_info
from .templates import load_project


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-800:]}")


def _has_audio(path: str) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def _atomic_out(out_path: str):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out, out.with_name(out.stem + ".part.mp4")


def composite_card_reveal(
    card_png: str,
    output_path: str,
    base_video: str | None = None,
    reveal_start: float = 2.0,
    reveal_end: float = 5.0,
    confetti_at: float | None = None,
    width: int = 1080,
    height: int = 1920,
) -> dict:
    """Draw the scroll-unroll reveal of the real card over a clip (or a built-in background)."""
    path = render_card_reveal(card_png, output_path, base_video, (width, height), 24, None, reveal_start, reveal_end,
                              confetti_at=confetti_at)
    return {"output": path, **video_info(path)}


def normalize_clip(src: str, dst: str, width: int, height: int, fps: int) -> None:
    """Re-encode to a common size / fps / codec / audio layout so clips can be joined without re-encoding."""
    out, tmp = _atomic_out(dst)
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps},format=yuv420p,setsar=1"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src]
    if _has_audio(src):
        cmd += ["-vf", vf, "-af", "aresample=44100,aformat=channel_layouts=stereo", "-map", "0:v", "-map", "0:a:0"]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
               "-vf", vf, "-map", "0:v", "-map", "1:a", "-shortest"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", str(tmp)]
    _run(cmd)
    os.replace(tmp, out)


def stitch_scenes(scene_paths: list[str], output_path: str, width: int = 1080, height: int = 1920, fps: int = 24,
                  music_path: str | None = None, music_volume: float = 0.5) -> dict:
    """Join scene clips in order into one video, optionally mixing in background music
    (looped to length and faded out)."""
    if not scene_paths:
        raise ValueError("scene_paths is empty")
    for p in scene_paths:
        if not Path(p).exists():
            raise FileNotFoundError(p)
    out, tmp_out = _atomic_out(output_path)
    with tempfile.TemporaryDirectory() as td:
        norm = []
        for i, p in enumerate(scene_paths):
            d = os.path.join(td, f"n{i:02d}.mp4")
            normalize_clip(p, d, width, height, fps)
            norm.append(d)
        lst = os.path.join(td, "list.txt")
        with open(lst, "w", encoding="utf-8") as f:
            for d in norm:
                f.write(f"file '{d}'\n")
        joined = os.path.join(td, "joined.mp4")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined])
        dur = video_info(joined)["duration"]
        if music_path and Path(music_path).exists():
            fade_at = max(0.0, dur - 1.5)
            fc = (f"[1:a]volume={music_volume},afade=t=out:st={fade_at:.2f}:d=1.5[m];"
                  f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
            _run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-stream_loop", "-1", "-i", music_path,
                  "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                  "-t", f"{dur:.3f}", str(tmp_out)])
        else:
            _run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-c", "copy", str(tmp_out)])
    os.replace(tmp_out, out)
    return {"output": str(out), **video_info(str(out)), "scenes_joined": len(scene_paths), "music": bool(music_path)}


def assemble_project(project_id: str, music_path: str | None = None, output_path: str | None = None) -> dict:
    """Stitch a project's finished scenes (using the card-composited version where there is one)."""
    from ..orchestrator import Orchestrator

    project = load_project(project_id)
    state = Orchestrator(project_id).load()
    paths, missing = [], []
    for sc in project["storyboard"]["scenes"]:
        rec = state["scenes"].get(sc["id"], {})
        card_rec = state["scenes"].get(f"{sc['id']}_card", {})
        chosen = card_rec.get("path") if card_rec.get("status") == "ok" else (rec.get("path") if rec.get("status") == "ok" else None)
        (paths if chosen else missing).append(chosen or sc["id"])
    if missing:
        return {"ok": False, "error": f"scenes not finished: {missing}. Run generate_all_scenes first."}
    size = project.get("assembly", {}).get("size", "1080x1920")
    w, h = (int(v) for v in size.split("x"))
    out = output_path or str(config.OUTPUT_DIR / f"{project_id}.mp4")
    music = music_path or project.get("assembly", {}).get("music")
    return {"ok": True, **stitch_scenes(paths, out, w, h, project.get("assembly", {}).get("fps", 24), music)}


def make_thumbnail(video_path: str, output_path: str, at_seconds: float = 1.0) -> dict:
    """Save one frame of a video as a JPEG (for previews / WhatsApp cover)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(at_seconds), "-i", video_path, "-frames:v", "1", "-q:v", "2", output_path])
    return {"output": output_path}


def register(mcp) -> None:
    for fn in (composite_card_reveal, stitch_scenes, assemble_project, make_thumbnail):
        mcp.tool()(fn)
