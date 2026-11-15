"""Tests for the local-model plumbing that need neither torch nor a GPU."""
import json

import pytest

from src import cli
from src.adapters import adapter_status, get_adapter
from src.adapters.ltx import LTXAdapter
from src.adapters.wan import WanAdapter
from scripts import download_models


def test_registry_has_local_models():
    assert {"veo", "ltx", "wan", "local"} <= set(adapter_status())
    assert isinstance(get_adapter("ltx"), LTXAdapter) and isinstance(get_adapter("wan"), WanAdapter)


def test_unavailable_without_torch_gives_reason():
    ok, why = LTXAdapter().is_available()
    if not ok:
        assert "torch" in why or "GPU" in why or "diffusers" in why


@pytest.mark.parametrize("cls,step", [(LTXAdapter, 8), (WanAdapter, 4)])
def test_frame_counts_follow_model_rule(cls, step):
    a = cls()
    for seconds in (1, 3, 5, 6, 8, 20):
        n = a.frames_for(seconds)
        assert (n - 1) % step == 0 and n <= a.default_max_frames


def test_frame_cap_and_env_override(monkeypatch):
    a = LTXAdapter()
    assert a.frames_for(20) == 121
    monkeypatch.setenv("LTX_MAX_FRAMES", "49")
    assert a.frames_for(20) == 49


def test_portrait_sizes_are_valid_multiples(monkeypatch):
    for cls, m in ((LTXAdapter, 32), (WanAdapter, 16)):
        w, h = cls().size_for("9:16")
        assert h > w and w % m == 0 and h % m == 0
    monkeypatch.setenv("LTX_WIDTH", "384")
    monkeypatch.setenv("LTX_HEIGHT", "640")
    assert LTXAdapter().size_for("9:16") == (384, 640)


def test_generate_without_start_photo_reports_error(tmp_path):
    from src.adapters import SceneRequest
    res = LTXAdapter().generate(SceneRequest("s1", "p", str(tmp_path / "o.mp4")))
    assert not res.ok and "start photo" in res.error


def test_download_list_and_dry_run(capsys):
    assert download_models.main(["--list"]) == 0
    assert download_models.main(["--preset", "ltx", "--preset", "wan", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Lightricks/LTX-Video" in out and "Wan2.1" in out


def test_cli_estimate_runs_without_gpu(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("WEDDING_STUDIO_HOME", str(tmp_path))
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"template": "south_indian_scroll_reveal"}))
    from src import config
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "TEMPLATES_DIR", tmp_path / "t")
    monkeypatch.setattr(config, "PROJECTS_DIR", tmp_path / "p")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "o")
    assert cli.main([str(job), "--estimate"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ai_clips"] and "recommendation" in out and "ltx" in out["adapters"]
