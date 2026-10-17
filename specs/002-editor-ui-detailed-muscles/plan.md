# Implementation Plan: Reel Editor App with Detailed Muscle Map

**Branch**: `002-editor-ui-detailed-muscles` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-editor-ui-detailed-muscles/spec.md`

## Summary

Add a desktop editor (PySide6) on top of the existing core. Creators load a clip, pick exercises,
mark segments on a timeline, drag and resize the front figure, back figure, legend and title
independently, and export. The body map gains a **Detailed** level of 40 muscles drawn from one
SVG source, with click-to-toggle muscles and zoomed **detail insets**.

The core stays the only renderer. The app displays the core's own sprites over decoded frames,
so preview and export are pixel-identical. The project file becomes edit script v2, readable by
the CLI. v1 scripts render unchanged.

## Technical Context

**Language/Version**: Python ≥ 3.9 (CI on 3.9 and 3.12)

**Primary Dependencies**: core: OpenCV, NumPy, Pillow, PyYAML (unchanged). New `app` extra: PySide6 ≥ 6.6, imageio-ffmpeg. New `dev` extras: pytest-qt, svgelements (bodymap build script only), PyInstaller (packaging CI).

**Storage**: files only: project YAML (v2), layout presets YAML in the user config dir, autosave YAML, proxy-video cache in `.musclereels-cache/`.

**Testing**: pytest (unit, golden images, preview/export parity, v1→v2 migration), pytest-qt offscreen app tests; GitHub Actions matrix (Linux/Windows/macOS).

**Target Platform**: Windows 10+, macOS 12+ (Linux best effort); packaged with PyInstaller one-folder builds.

**Project Type**: desktop app + CLI sharing one Python library.

**Performance Goals**: preview ≥ 24 fps at 540×960 for 1080p clips; drag feedback < 16 ms; element re-raster on resize < 50 ms; export ≤ 3× real time (unchanged); app cold start < 4 s.

**Constraints**: offline only; bounded memory (frame cache ≤ ~300 MB, no whole-video buffering); core modules never import Qt; v1 scripts render identically.

**Scale/Scope**: 1 window with 4 panels; 40 detailed muscles in 18 groups; 9 inset regions; ~36 exercises remapped to detailed muscles; 5 built-in layout presets.

All unknowns are resolved in [research.md](research.md) (R1–R12).

## Constitution Check

*GATE: checked before Phase 0 and again after Phase 1 design.*

| Principle | Check | Status |
|---|---|---|
| I. Local-First & Private | No network at runtime; ffmpeg bundled locally (R4); autosave/cache on local disk. | ✅ Pass |
| II. Reel-Ready Output | Export path unchanged (1080×1920 H.264/AAC, faststart). Safe-zone snapping is the default; overriding is explicit per element (R8). | ✅ Pass |
| III. Anatomically Honest | Detailed remaps follow consensus; ambiguous parent groups resolved by under-claiming (R6); PRs that change exercises must give reasoning. | ✅ Pass |
| IV. CLI-First, Data-Driven | All new render options exist in edit script v2 and CLI flags (contracts/cli.md). App uses only core-api.md. Muscles, regions, presets and art are data files. | ✅ Pass |
| V. Test-First | Tests are derived from acceptance scenarios; golden images serve as PR previews; parity test guards SC-004. | ✅ Pass |
| VI. Simplicity | PySide6 + imageio-ffmpeg are heavy, so they're isolated in the optional `app` extra; the core path adds no runtime dependency. svgelements is dev-only. | ✅ Pass (justified in Complexity Tracking) |
| Tech: determinism, bounded memory, MINOR-version compatibility | Same renderer for preview/export; LRU frame cache; v1 accepted. Version → **0.2.0**. | ✅ Pass |

**Post-design re-check (after Phase 1)**: the data model, contracts and structure introduce no new violations. Card modes and presets keep 001 output reproducible (SC-005). The proxy video only changes inputs that OpenCV would mis-time anyway. ✅

## Project Structure

### Documentation (this feature)

```text
specs/002-editor-ui-detailed-muscles/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R12 decisions
├── data-model.md        # entities, 40-muscle table, project schema
├── quickstart.md        # end-to-end validation
├── contracts/
│   ├── edit-script-v2.md
│   ├── cli.md
│   ├── core-api.md
│   └── ui.md
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
assets/
└── bodymap.svg                 # NEW: editable art, one path id per muscle (front + back)

tools/
├── build_bodymap.py            # NEW: SVG → data/bodymap/*.json (dev only)
└── compare_videos.py           # NEW: frame-by-frame equality check for parity/compat

musclereels/
├── muscles.py                  # NEW: registry: 40 muscles, 18 groups, aliases, resolution
├── bodymap.py                  # CHANGED: loads JSON art, two levels, smoothing, hit_test, region_box
├── layout.py                   # NEW: ElementPlacement, Layout, presets, safe-zone snapping
├── inset.py                    # NEW: detail inset rendering + callouts
├── overlay.py                  # CHANGED: per-element sprites, card modes, scale for preview
├── video.py                    # NEW: VideoSource, probing, CFR proxy, frame_at, fit_frame (moved)
├── project.py                  # CHANGED: v2 schema, v1 migration, save_project, activation
├── exercises.py                # CHANGED: MuscleRef (groups + muscles)
├── render.py                   # CHANGED: uses video.py, layouts, insets, progress/cancel
├── cli.py                      # CHANGED: app, --detail, --layout-preset, --inset, list flags
├── theme.py
├── data/
│   ├── exercises.yaml          # CHANGED: detailed muscle mappings
│   ├── muscles.yaml            # NEW: ids, names, groups, views
│   ├── presets.yaml            # NEW: built-in layout presets
│   └── bodymap/
│       ├── front.json          # NEW (generated)
│       ├── back.json           # NEW (generated)
│       └── regions.json        # NEW: inset crop boxes
└── app/                        # NEW: PySide6 editor (imports core only via core-api.md)
    ├── __init__.py             # launch(); friendly error if PySide6 missing
    ├── main_window.py          # menus, panels, state machine (open/dirty/export)
    ├── canvas.py               # QGraphicsScene: video item, element items, safe zones, handles
    ├── figure_item.py          # draggable/resizable figure/inset items, hover/click muscles
    ├── timeline.py             # segments, playhead, trim handles
    ├── inspector.py            # segment/element/inset properties
    ├── exercise_panel.py       # search list, custom exercise
    ├── player.py               # QThread frame delivery + LRU cache
    ├── commands.py             # QUndoCommand subclasses for every edit
    ├── export_dialog.py        # render() in worker thread with progress/cancel
    ├── autosave.py
    └── presets_store.py        # user preset files in AppConfigLocation

tests/
├── test_core.py                # existing
├── test_muscles.py             # NEW
├── test_layout.py              # NEW
├── test_project_v2.py          # NEW: migration, round-trip, validation errors
├── test_inset.py               # NEW
├── test_parity.py              # NEW: preview path == export path
├── golden/                     # NEW: reference PNGs + test_golden.py
└── app/                        # NEW: pytest-qt smoke tests

packaging/
├── musclereels.spec            # NEW: PyInstaller spec
└── ../.github/workflows/
    ├── tests.yml               # NEW: pytest matrix
    └── build-app.yml           # NEW: Windows zip + macOS dmg artifacts
```

**Structure Decision**: one Python package with the Qt app as the `musclereels.app` sub-package, enabled by the optional `app` extra. The core is split into focused modules (`muscles`, `layout`, `inset`, `video`) so the app and CLI share them through the contract in `contracts/core-api.md`. No separate frontend/backend.

## Delivery order (input for /speckit-tasks)

1. **Foundation**: `muscles.py` + `muscles.yaml`, SVG pipeline and detailed art, `bodymap.py` refactor (two levels, hit test, regions). Golden tests. *Unblocks Story 4.*
2. **Story 4 core**: exercise remap, activation resolution, legend grouping, CLI `--detail`.
3. **Layout core**: `layout.py`, element sprites, card modes, presets, v2 schema + migration, compatibility test against `main`.
4. **Story 1 app MVP**: window, video player, canvas, exercise panel, export dialog, save/open.
5. **Story 2 app**: drag/resize/snap, visibility toggles, presets UI, per-segment overrides, undo/redo.
6. **Story 3 app**: timeline segments and trim.
7. **Story 4 app**: hover/click muscles, detail toggle.
8. **Story 5**: insets in core, CLI `--inset`, app inset controls.
9. **Hardening**: autosave/recovery, VFR proxy, parity test, packaging CI, README.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Heavy GUI dependency (PySide6, ~100 MB) | The spec requires a drag-and-drop editor with live video preview on Windows and macOS. | Tkinter can't give smooth video or transformable items; a web UI needs a server and a second renderer (R1). Isolated in the optional `app` extra, so CLI users aren't affected. |
| Bundled ffmpeg (imageio-ffmpeg) | Everyday use must not need a terminal install of ffmpeg. | Requiring a system ffmpeg is fine for the CLI (kept as the first choice) but breaks the "just open the app" goal. |
| SVG asset + build script | 40 hand-typed polygons are unmaintainable and can't be reviewed visually. | Inline Python polygons (001 approach) don't scale; runtime SVG parsing would add a core dependency. |
