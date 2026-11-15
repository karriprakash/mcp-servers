"""Storyboard: turns a template + variables into per-scene prompts with identity locks."""
from __future__ import annotations

import string

from .. import config


class _SafeDict(dict):
    def __missing__(self, key):  # leave unknown {placeholders} visible instead of crashing
        return "{" + key + "}"


def fill(text: str, variables: dict) -> str:
    return string.Formatter().vformat(text, (), _SafeDict(variables))


def render_storyboard(template: dict, variables: dict) -> dict:
    chars = {k: fill(v, variables) for k, v in template.get("characters", {}).items()}
    setting = fill(variables.get("setting", ""), variables)
    scenes = []
    for sc in template["scenes"]:
        parts = [
            fill(template.get("style", ""), variables),
            f"Setting: {setting}" if setting else "",
            f"Groom (left): {chars.get('groom', '')}" if chars.get("groom") else "",
            f"Bride (right): {chars.get('bride', '')}" if chars.get("bride") else "",
            f"Action: {fill(sc.get('action', ''), variables)}",
            f"Rules: {fill(template.get('rules', ''), variables)}" if template.get("rules") else "",
        ]
        scenes.append({
            "id": sc["id"],
            "title": sc.get("title", sc["id"]),
            "kind": sc.get("kind", "ai_clip"),
            "duration": sc.get("duration", 6),
            "prompt": " ".join(p for p in parts if p),
            "negative_prompt": template.get("negative_prompt", ""),
            "post": sc.get("post"),
        })
    w, h = (int(v) for v in template.get("assembly", {}).get("size", "1080x1920").split("x"))
    return {
        "aspect_ratio": "9:16" if w < h else "16:9",
        "total_seconds": sum(s["duration"] for s in scenes),
        "scenes": scenes,
    }


def build_storyboard(template_name: str, overrides: dict | None = None) -> dict:
    """Preview a template's storyboard (prompts per scene) without creating a project."""
    from .templates import get_template

    tpl = get_template(template_name)
    return render_storyboard(tpl, {**tpl.get("variables", {}), **(overrides or {})})


def register(mcp) -> None:
    mcp.tool()(build_storyboard)
