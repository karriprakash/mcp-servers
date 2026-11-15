# Cinematic Wedding Studio MCP (v2.1)

An MCP server that turns couple photos and a real wedding card into a short animated
announcement video, and keeps each finished project as a reusable template.

## What is tested and what is not

| Part | Status |
|---|---|
| Template fill, projects, save-as-template | tested (pytest) |
| Local card-reveal compositor (rod, scroll unroll, real card, confetti) | tested on real files; Telugu text stays pixel-sharp |
| Stitching with normalising and music mix | tested |
| Motion QC (jumps, flicker, frozen clip), reference beat finder | tested |
| Server starts and registers all tools (mcp 1.x and 2.x) | tested |
| Google Veo adapter | **written, not run** (no API key was available); set `VEO_MODEL` to a model your key can use |
| Face identity QC with `insightface` | **written, not run** (not installed here). Without it the check is skipped and says so |

Wan, LTX, CogVideoX and ComfyUI adapters are not included yet. Add one by subclassing
`VideoAdapter` in `src/adapters/` and registering it in `src/adapters/__init__.py`.

## Layout

```
src/server.py            MCP entrypoint
src/orchestrator.py      tries adapters in order, retries, runs QC, checkpoints each scene
src/adapters/            base.py, veo.py, local_compositor.py
src/engines/             motion_qc.py, face_qc.py
src/tools/               analysis, storyboard, templates, generation, assembly
templates/               south_indian_scroll_reveal.json
tests/test_pipeline.py
```

## Install and run

```
pip install -r requirements.txt        # needs ffmpeg on PATH
export GEMINI_API_KEY=...              # only for AI clips (Veo)
python -m src.server                   # stdio MCP server
pytest -q
```

## Tools

- analysis: `adapter_status`, `analyze_reference_video`, `inspect_photo`, `check_clip_quality`
- templates: `list_templates`, `get_template`, `save_template`, `create_project`, `save_project_as_template`
- storyboard: `build_storyboard`
- generation: `generate_scene`, `generate_all_scenes`, `project_status`
- assembly: `composite_card_reveal`, `stitch_scenes`, `assemble_project`, `make_thumbnail`

## Typical flow

1. `create_project("south_indian_scroll_reveal", {groom_name, bride_name, event_date, ...}, card_png=..., reference_photos=[...], person_photos={...})`
2. `generate_all_scenes(project_id)`: AI clips come from Veo, then the real card is composited onto the scroll scene.
   Safe to re-run after a failure; finished scenes are skipped.
3. `assemble_project(project_id, music_path=...)` writes the final MP4 to `$WEDDING_STUDIO_HOME/outputs`.
4. `save_project_as_template(project_id, "my preset")` so the next couple only overrides what differs.

No AI key? `composite_card_reveal` alone gives a complete card-reveal clip over a built-in background.

## Design notes

- The card is never sent through an AI model, so Telugu (or any) text is never redrawn or warped.
- All outputs are written to a temporary `.part.mp4` and renamed when finished, so a stopped job never leaves a file that looks complete.
- Identity: Veo gets up to 3 reference photos; the optional ArcFace check compares sampled frames with one-person portraits.
