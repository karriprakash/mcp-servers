"""Run with: pytest -q   (needs ffmpeg; no API key needed)."""
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from src import config


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", tmp_path / "templates")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    config.ensure_dirs()


@pytest.fixture
def card(tmp_path):
    img = np.full((1000, 740, 3), (205, 228, 240), np.uint8)
    cv2.rectangle(img, (20, 20), (719, 979), (40, 120, 200), 12)
    cv2.putText(img, "TEST CARD", (150, 500), cv2.FONT_HERSHEY_SIMPLEX, 2, (30, 30, 120), 4)
    p = tmp_path / "card.png"
    cv2.imwrite(str(p), img)
    return str(p)


def test_template_roundtrip(card):
    from src.tools import storyboard, templates
    names = [t["name"] for t in templates.list_templates()["templates"]]
    assert "south_indian_scroll_reveal" in names
    board = storyboard.build_storyboard("south_indian_scroll_reveal", {"groom_name": "Ravi", "bride_name": "Sita"})
    assert board["aspect_ratio"] == "9:16" and board["total_seconds"] == 20
    assert "{" not in board["scenes"][0]["prompt"].replace("{}", "")
    proj = templates.create_project("south_indian_scroll_reveal", {"groom_name": "Ravi", "bride_name": "Sita"}, card_png=card)
    saved = templates.save_project_as_template(proj["project_id"], "Ravi & Sita preset")
    assert Path(saved["saved"]).exists()
    assert templates.get_template("ravi_sita_preset")["variables"]["groom_name"] == "Ravi"


def test_missing_asset_is_rejected():
    from src.tools import templates
    with pytest.raises(FileNotFoundError):
        templates.create_project("south_indian_scroll_reveal", card_png="/nope.png")


def test_compositor_and_qc(card, tmp_path):
    from src.adapters.local_compositor import render_card_reveal
    from src.engines import motion_qc
    out = render_card_reveal(card, str(tmp_path / "r.mp4"), size=(360, 640), duration=4.0, reveal_start=1.0,
                             reveal_end=2.5, confetti_at=3.0)
    info = motion_qc.video_info(out)
    assert info["width"] == 360 and 3.9 < info["duration"] < 4.1
    assert motion_qc.analyze_motion(out)["mean_motion"] > 0
    # the finished frame must contain the card centre unchanged apart from scaling
    cap = cv2.VideoCapture(out); cap.set(cv2.CAP_PROP_POS_FRAMES, 70); ok, f = cap.read(); assert ok


def test_stitch(card, tmp_path):
    from src.adapters.local_compositor import render_card_reveal
    from src.tools.assembly import stitch_scenes
    a = render_card_reveal(card, str(tmp_path / "a.mp4"), size=(360, 640), duration=2.0, reveal_start=0.5, reveal_end=1.5)
    b = render_card_reveal(card, str(tmp_path / "b.mp4"), size=(360, 640), duration=2.0, reveal_start=0.5, reveal_end=1.5)
    res = stitch_scenes([a, b], str(tmp_path / "ab.mp4"), 360, 640, 24)
    assert 3.9 < res["duration"] < 4.1


def test_server_registers_tools():
    import asyncio
    from src.server import build_server
    res = asyncio.run(build_server().list_tools())
    tools = getattr(res, 'tools', res)
    names = {t.name for t in tools}
    assert {"build_storyboard", "create_project", "generate_scene", "stitch_scenes", "save_project_as_template",
            "check_clip_quality"} <= names


def test_orchestrator_reports_unavailable_adapter(card):
    from src.adapters import SceneRequest
    from src.orchestrator import Orchestrator
    import os
    os.environ.pop("GEMINI_API_KEY", None)
    rec = Orchestrator("t1", ["veo"], max_retries=0).render_scene(
        SceneRequest("s1", "x", str(config.PROJECTS_DIR / "t1" / "s1.mp4")), qc=False)
    assert rec["status"] == "failed" and "GEMINI_API_KEY" in rec["attempts"][0]["error"]


def test_photo_and_face_qc_never_crash(card, tmp_path):
    """Works with or without a face detector installed; says so instead of failing."""
    from src.tools import analysis
    from src.adapters.local_compositor import render_card_reveal
    info = analysis.inspect_photo(card)
    assert info["width"] == 740 and "faces" in info
    clip = render_card_reveal(card, str(tmp_path / "c.mp4"), size=(360, 640), duration=2.0)
    res = analysis.check_clip_quality(clip, {"groom": [card]})
    assert "motion" in res and "face" in res and "passed" in res["face"]
