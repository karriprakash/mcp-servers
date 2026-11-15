"""Run a whole job from a JSON file, with no MCP client (for a GPU VM or a laptop).

    python -m src.cli examples/job.example.json --estimate     # what would run, on this hardware
    python -m src.cli job.json --only-scene s1                 # try one clip first
    python -m src.cli job.json                                 # all scenes, then assemble

Finished scenes are checkpointed, so re-running after a failure or a stopped VM resumes."""
from __future__ import annotations

import argparse
import json
import sys

from . import config
from .adapters import adapter_status, hw
from .tools import assembly, generation, templates


def _load_job(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        job = json.load(f)
    if "template" not in job:
        raise SystemExit("job file needs a 'template' key")
    return job


def estimate(job: dict) -> dict:
    tpl = templates.get_template(job["template"])
    scenes = tpl.get("scenes", [])
    device, info = hw.detect_device()
    return {
        "device": device, **info,
        "recommendation": hw.recommend(device, info),
        "adapters": adapter_status(),
        "ai_clips": [s["id"] for s in scenes if s.get("kind") == "ai_clip"],
        "local_scenes": [s["id"] for s in scenes if s.get("kind") != "ai_clip"],
        "time_note": "not measured by this project: time one clip with --only-scene first, then multiply by the clip count",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("job", help="job JSON (see examples/job.example.json)")
    ap.add_argument("--estimate", action="store_true", help="print hardware and plan, run nothing")
    ap.add_argument("--only-scene", help="render just this scene id and stop")
    ap.add_argument("--no-assemble", action="store_true")
    a = ap.parse_args(argv)

    job = _load_job(a.job)
    config.ensure_dirs()
    if a.estimate:
        print(json.dumps(estimate(job), indent=2))
        return 0

    pid = job.get("project_id")
    if pid and (config.PROJECTS_DIR / pid / "project.json").exists():
        print(f"resuming project {pid}")
    else:
        made = templates.create_project(
            job["template"], job.get("variables"), job.get("card_png"),
            job.get("reference_photos"), job.get("person_photos"), pid)
        pid = made["project_id"]
        print(f"created project {pid}  (add \"project_id\": \"{pid}\" to the job file to resume it later)")

    adapters = job.get("adapters") or ["ltx"]
    if a.only_scene:
        res = generation.generate_scene(pid, a.only_scene, adapters)
        print(json.dumps(res, indent=2, default=str))
        return 0 if res.get("status") == "ok" else 1

    report = generation.generate_all_scenes(pid, adapters)
    print(json.dumps({"finished": report["finished"], "failed": report["failed"]}, indent=2))
    if report["failed"]:
        print("some scenes failed: see project_status; re-run to resume", file=sys.stderr)
        return 1
    if not a.no_assemble:
        out = assembly.assemble_project(pid, job.get("music"))
        print(json.dumps(out, indent=2, default=str))
        return 0 if out.get("ok") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
