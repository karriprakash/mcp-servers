"""Scene orchestrator: tries adapters in order, retries, runs QC, and checkpoints every step so
an interrupted job can resume without paying for finished scenes again."""
from __future__ import annotations

import time
from pathlib import Path

from . import config
from .adapters import SceneRequest, SceneResult, get_adapter
from .engines import face_qc, motion_qc


class Orchestrator:
    def __init__(self, project_id: str, adapters: list[str] | None = None, max_retries: int = 2, backoff: float = 5.0):
        self.project_id = project_id
        self.adapters = adapters or ["veo"]
        self.max_retries = max_retries
        self.backoff = backoff
        self.ckpt_path = config.PROJECTS_DIR / project_id / "checkpoint.json"

    # ---- checkpoint -------------------------------------------------------------------------
    def load(self) -> dict:
        if self.ckpt_path.exists():
            return config.read_json(self.ckpt_path)
        return {"project_id": self.project_id, "scenes": {}}

    def save(self, state: dict) -> None:
        config.write_json_atomic(self.ckpt_path, state)

    # ---- one scene --------------------------------------------------------------------------
    def render_scene(
        self,
        req: SceneRequest,
        identity_refs: dict[str, list[str]] | None = None,
        expected_faces: int | None = None,
        qc: bool = True,
        resume: bool = True,
    ) -> dict:
        state = self.load()
        rec = state["scenes"].get(req.scene_id, {})
        if resume and rec.get("status") == "ok" and Path(rec.get("path", "")).exists():
            rec["resumed"] = True
            return rec

        attempts: list[dict] = []
        rec = {"status": "failed", "attempts": attempts}
        for name in self.adapters:
            adapter = get_adapter(name)
            usable, why = adapter.is_available()
            if not usable:
                attempts.append({"adapter": name, "ok": False, "error": f"unavailable: {why}"})
                continue
            for n in range(self.max_retries + 1):
                res: SceneResult = adapter.generate(req)
                entry = {"adapter": name, "try": n + 1, "ok": res.ok, "error": res.error, "meta": res.meta}
                attempts.append(entry)
                if not res.ok:
                    if n < self.max_retries:
                        time.sleep(self.backoff * (n + 1))
                    continue
                if qc:
                    report = self.quality_check(res.path, identity_refs, expected_faces)
                    entry["qc"] = report
                    if not report["passed"]:
                        entry["ok"] = False
                        entry["error"] = "quality check failed: " + "; ".join(report["flags"])
                        continue
                rec.update({"status": "ok", "path": res.path, "adapter": name})
                state["scenes"][req.scene_id] = rec
                self.save(state)
                return rec

        state["scenes"][req.scene_id] = rec
        self.save(state)
        return rec

    @staticmethod
    def quality_check(path: str, identity_refs: dict[str, list[str]] | None, expected_faces: int | None) -> dict:
        motion = motion_qc.analyze_motion(path)
        flags = list(motion["flags"])
        out = {"motion": motion, "flags": flags}
        if identity_refs:
            face = face_qc.check_identity(path, identity_refs, expected_faces=expected_faces)
            out["face"] = face
            # The weak OpenCV fallback is advisory only: it must not reject a good clip.
            if face["reliable"]:
                flags.extend(face["flags"])
        out["passed"] = not flags
        return out
