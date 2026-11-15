"""Templates: a template is a reusable storyboard with {placeholders}; a project is one filled-in
copy for a specific couple. Finished projects can be saved back as new templates."""
from __future__ import annotations

import re
import time
from pathlib import Path

from .. import config

_SAFE = re.compile(r"[^a-z0-9_]+")


def slugify(name: str) -> str:
    s = _SAFE.sub("_", name.strip().lower()).strip("_")
    if not s:
        raise ValueError("name must contain letters or digits")
    return s


def _find_template(name: str) -> Path:
    slug = slugify(name)
    for base in (config.TEMPLATES_DIR, config.BUILTIN_TEMPLATES_DIR):
        p = base / f"{slug}.json"
        if p.exists():
            return p
    raise FileNotFoundError(f"No template named '{name}'. Use list_templates to see what exists.")


def list_templates() -> dict:
    """List built-in and saved templates."""
    config.ensure_dirs()
    out = []
    for origin, base in (("saved", config.TEMPLATES_DIR), ("built-in", config.BUILTIN_TEMPLATES_DIR)):
        if not base.exists():
            continue
        for p in sorted(base.glob("*.json")):
            data = config.read_json(p)
            out.append({
                "name": data.get("name", p.stem),
                "origin": origin,
                "description": data.get("description", ""),
                "scenes": len(data.get("scenes", [])),
                "variables": sorted(data.get("variables", {})),
            })
    return {"templates": out}


def get_template(name: str) -> dict:
    """Return a template's full JSON."""
    return config.read_json(_find_template(name))


def save_template(name: str, template: dict, description: str | None = None) -> dict:
    """Save a template JSON under a name (overwrites a saved template of the same name)."""
    config.ensure_dirs()
    slug = slugify(name)
    data = dict(template)
    data["name"] = slug
    if description:
        data["description"] = description
    for key in ("scenes", "variables"):
        if key not in data:
            raise ValueError(f"template is missing '{key}'")
    path = config.TEMPLATES_DIR / f"{slug}.json"
    config.write_json_atomic(path, data)
    return {"saved": str(path), "name": slug}


def create_project(
    template_name: str,
    overrides: dict | None = None,
    card_png: str | None = None,
    reference_photos: list[str] | None = None,
    person_photos: dict[str, list[str]] | None = None,
    project_id: str | None = None,
) -> dict:
    """Fill a template for one couple and create a project folder.

    overrides: values for the template variables (groom_name, bride_name, event_date, ...).
    card_png: the real wedding card image, composited onto the scroll later.
    reference_photos: couple photos sent to the video model as identity references.
    person_photos: {"groom": [portrait], "bride": [portrait]} used for the face identity check.
    """
    from . import storyboard  # local import avoids a cycle

    config.ensure_dirs()
    tpl = get_template(template_name)
    variables = {**tpl.get("variables", {}), **(overrides or {})}
    for label, paths in (("card_png", [card_png] if card_png else []),
                         ("reference_photos", reference_photos or []),
                         *[(f"person_photos[{k}]", v) for k, v in (person_photos or {}).items()]):
        for p in paths:
            if not Path(p).exists():
                raise FileNotFoundError(f"{label}: file not found: {p}")

    slug = slugify(f"{variables.get('groom_name', 'groom')}_{variables.get('bride_name', 'bride')}")
    pid = project_id or f"{slug}_{time.strftime('%Y%m%d_%H%M%S')}"
    board = storyboard.render_storyboard(tpl, variables)
    project = {
        "project_id": pid,
        "template": tpl["name"],
        "variables": variables,
        "assets": {"card_png": card_png, "reference_photos": reference_photos or [], "person_photos": person_photos or {}},
        "storyboard": board,
        "assembly": tpl.get("assembly", {}),
    }
    config.write_json_atomic(config.PROJECTS_DIR / pid / "project.json", project)
    return {"project_id": pid, "project_file": str(config.PROJECTS_DIR / pid / "project.json"), "scenes": [s["id"] for s in board["scenes"]]}


def load_project(project_id: str) -> dict:
    p = config.PROJECTS_DIR / project_id / "project.json"
    if not p.exists():
        raise FileNotFoundError(f"No project '{project_id}'")
    return config.read_json(p)


def save_project_as_template(project_id: str, template_name: str, description: str = "") -> dict:
    """Turn a finished project back into a template. The couple's details become the default
    variable values, so the next couple only overrides what differs."""
    project = load_project(project_id)
    tpl = get_template(project["template"])
    tpl["variables"] = project["variables"]
    tpl["derived_from"] = project_id
    return save_template(template_name, tpl, description or f"Saved from project {project_id}")


def register(mcp) -> None:
    for fn in (list_templates, get_template, save_template, create_project, save_project_as_template):
        mcp.tool()(fn)
