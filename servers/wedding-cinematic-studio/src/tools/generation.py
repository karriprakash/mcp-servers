"""Generation tools: render scenes of a project through the orchestrator."""
from __future__ import annotations

from pathlib import Path

from .. import config
from ..adapters import SceneRequest
from ..orchestrator import Orchestrator
from .templates import load_project


def _scene_by_id(project: dict, scene_id: str) -> dict:
    for s in project["storyboard"]["scenes"]:
        if s["id"] == scene_id:
            return s
    raise KeyError(f"No scene '{scene_id}' in project {project['project_id']}")


def generate_scene(
    project_id: str,
    scene_id: str,
    adapters: list[str] | None = None,
    quality_check: bool = True,
    resume: bool = True,
) -> dict:
    """Render one scene.

    ai_clip scenes go to the video provider(s) in `adapters` (default: veo) with the project's
    reference photos, then are checked for jumps/flicker and (if portraits were given) identity.
    If the scene has a `post: card_reveal` step, the real card is composited over the clip.
    card_reveal scenes are drawn locally with no API."""
    project = load_project(project_id)
    scene = _scene_by_id(project, scene_id)
    out_dir = config.PROJECTS_DIR / project_id / "scenes"
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = project["assets"]

    if scene["kind"] == "card_reveal":
        orch = Orchestrator(project_id, ["local"])
        req = SceneRequest(
            scene_id=scene_id, prompt="", out_path=str(out_dir / f"{scene_id}.mp4"),
            duration=scene["duration"], aspect_ratio=project["storyboard"]["aspect_ratio"],
            extra={"card_png": assets.get("card_png"), **(scene.get("post") or {})},
        )
        return orch.render_scene(req, qc=False, resume=resume)

    orch = Orchestrator(project_id, adapters or ["veo"])
    req = SceneRequest(
        scene_id=scene_id, prompt=scene["prompt"], out_path=str(out_dir / f"{scene_id}.mp4"),
        duration=scene["duration"], aspect_ratio=project["storyboard"]["aspect_ratio"],
        reference_images=assets.get("reference_photos", []),
        extra={"negative_prompt": scene.get("negative_prompt", "")},
    )
    result = orch.render_scene(
        req, identity_refs=assets.get("person_photos") or None, expected_faces=2, qc=quality_check, resume=resume,
    )
    post = scene.get("post")
    if result["status"] == "ok" and post and post.get("type") == "card_reveal":
        if not assets.get("card_png"):
            result["post_error"] = "scene needs a card_reveal but the project has no card_png"
            return result
        local = Orchestrator(project_id, ["local"])
        creq = SceneRequest(
            scene_id=f"{scene_id}_card", prompt="", out_path=str(out_dir / f"{scene_id}_card.mp4"),
            duration=0, aspect_ratio=project["storyboard"]["aspect_ratio"],
            extra={"card_png": assets["card_png"], "base_video": result["path"],
                   **{k: v for k, v in post.items() if k != "type"}},
        )
        post_res = local.render_scene(creq, qc=False, resume=resume)
        result["post"] = post_res
        if post_res["status"] == "ok":
            result["final_path"] = post_res["path"]
    else:
        result["final_path"] = result.get("path")
    return result


def generate_all_scenes(project_id: str, adapters: list[str] | None = None, quality_check: bool = True) -> dict:
    """Render every scene in order, skipping ones already finished (safe to re-run after a failure)."""
    project = load_project(project_id)
    report = {}
    for sc in project["storyboard"]["scenes"]:
        report[sc["id"]] = generate_scene(project_id, sc["id"], adapters, quality_check)
    done = [k for k, v in report.items() if v.get("status") == "ok"]
    return {"project_id": project_id, "finished": done, "failed": [k for k in report if k not in done], "scenes": report}


def project_status(project_id: str) -> dict:
    """Which scenes of a project are finished, and the last error for the ones that are not."""
    project = load_project(project_id)
    state = Orchestrator(project_id).load()
    rows = []
    for sc in project["storyboard"]["scenes"]:
        rec = state["scenes"].get(sc["id"], {})
        last_err = next((a.get("error") for a in reversed(rec.get("attempts", [])) if a.get("error")), None)
        rows.append({"scene": sc["id"], "title": sc["title"], "status": rec.get("status", "pending"),
                     "path": rec.get("path"), "last_error": last_err})
    return {"project_id": project_id, "scenes": rows}


def register(mcp) -> None:
    for fn in (generate_scene, generate_all_scenes, project_status):
        mcp.tool()(fn)
