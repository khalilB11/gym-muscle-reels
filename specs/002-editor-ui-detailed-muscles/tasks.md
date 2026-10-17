---
description: "Task list for feature 002: Reel Editor App with Detailed Muscle Map"
---

# Tasks: Reel Editor App with Detailed Muscle Map

**Input**: Design documents from `specs/002-editor-ui-detailed-muscles/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. Constitution V (Test-First, non-negotiable) requires tests written from the acceptance scenarios before implementation, and they must fail first.

**Organization**: Grouped by user story, in priority order: US1, US2, US4 (P1), then US3, US5 (P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: user story from spec.md (US1–US5)
- Paths are from the repository root; single Python package `musclereels/`, tests in `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependencies, tooling and folders for the new modules

- [X] T001 Bump version to 0.2.0 and add extras in pyproject.toml: `app = ["PySide6>=6.6", "imageio-ffmpeg>=0.5"]`, `dev = ["pytest>=7", "pytest-qt>=4", "svgelements>=1.9"]`; include `data/*.yaml`, `data/bodymap/*.json` as package data; update `musclereels/__init__.py` `__version__`
- [X] T002 [P] Create empty package/folders per plan.md: `musclereels/app/__init__.py`, `musclereels/data/bodymap/`, `assets/`, `tools/`, `tests/golden/`, `tests/app/`, `packaging/`
- [X] T003 [P] Add `tests/conftest.py` with fixtures: `demo_clip` (generates a 3 s 720×1280 30 fps clip with a tone audio track via ffmpeg into tmp_path, session-scoped), `landscape_clip` (1280×720), and a `--update-golden` pytest option
- [X] T004 [P] Create `.github/workflows/tests.yml`: matrix ubuntu/windows/macos × Python 3.9/3.12, install ffmpeg, `pip install -e ".[app,dev]"`, run `pytest` with `QT_QPA_PLATFORM=offscreen`
- [X] T005 [P] Write `tools/compare_videos.py`: compare two videos frame by frame (frame count, size, per-pixel max abs diff ≤ tolerance arg, default 0), exit 0/1 with a summary of the first differing frame

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: core refactors every story depends on: muscle registry, element-based layout, project v2, video source, cancellable render. Output for 001 inputs must stay identical.

**⚠️ CRITICAL**: no user story work starts until this phase is complete.

### Tests (write first, must fail)

- [X] T006 [P] Write compatibility test `tests/test_compat_v1.py`: for `examples/session.yaml` (with input replaced by the `demo_clip` fixture) and the quick mode `-e squat`, the rendered frames at t = 0.5, 2.0, 2.9 s match reference PNGs produced from v0.1.0 (generate them once from a checkout of `main` at commit `6e23914` and store in `tests/golden/v1/`)
- [X] T007 [P] Write `tests/test_project_v2.py`: v1 file without `version` loads and maps `position: left` → layout preset `card-left`; v2 round-trip `load_project` → `save_project` → `load_project` is equal; an unknown key raises `ProjectError` naming the key and line; overlapping segments rejected; `0 ≤ start < end` enforced; `detail_level` default `simple`
- [X] T008 [P] Write `tests/test_layout.py`: `builtin_presets()` contains `card-left`, `card-right`, `card-center`, `split-corners`, `back-only-large`; `snap_to_safe_zone` clamps a box into x∈[60, 900], y∈[250, 1470] (canvas 1080×1920 minus 250 top / 450 bottom / 60 left / 180 right) unless `allow_outside_safe_zone: true`; `effective_layout` applies a partial segment override and leaves other fields at the project default
- [X] T009 [P] Write `tests/test_video.py`: `VideoSource(demo_clip).info` reports duration≈3.0, fps 30, has_audio True, needs_proxy False; `frame_at(1.5)` equals sequential decode frame 45; a VFR clip (built with ffmpeg `-vf setpts` jitter) reports `needs_proxy True` and after `prepare()` `frame_at` is exact; `fit_frame` returns 1080×1920 for portrait, landscape, square
- [X] T010 [P] Write `tests/test_render_cancel.py`: `render(project, progress_cb, cancel)` calls `progress_cb` with increasing fractions in [0, 1]; setting `cancel` mid-render stops it, removes the partial output and raises `RenderCancelled`

### Implementation

- [X] T011 Create `musclereels/muscles.py` and `musclereels/data/muscles.yaml` holding today's 18 Simple groups and aliases (moved from `bodymap.py`), exposing `registry()`, `MuscleRegistry.resolve(refs)`, `group_of(id)`, `muscles(level)`; keep `bodymap.resolve_muscles`/`display_name` as thin wrappers so existing tests pass
- [X] T012 Create `musclereels/layout.py` per data-model.md: `ElementPlacement(visible: bool, x: int, y: int, width: int, allow_outside_safe_zone: bool=False)` with "height derived from aspect", `Layout(title, front, back, legend, card: 'grouped'|'per_element'|'none', labels: bool)`, `SegmentLayoutOverride` (partial), `snap_to_safe_zone`, `effective_layout`, `load_preset`/`save_preset`
- [X] T013 Add built-in presets in `musclereels/data/presets.yaml` and `layout.builtin_presets()`: `card-left/right/center` computed with the same geometry as 001's `_card_sprite` (figure width 210·scale, pad 22·scale, card y below title) so output is unchanged; plus `split-corners` (front bottom-left, back top-right, `card: per_element`) and `back-only-large` (front hidden, back width 360)
- [X] T014 Refactor `musclereels/overlay.py` into per-element sprites: `build_sprites(project, segment, layout, scale=1.0)` returns sprites for title, front, back, legend (and, later, insets); card modes `grouped` (one panel around union of visible front/back/legend), `per_element`, `none`; `labels` toggles FRONT/BACK; keep `composite()` unchanged; `scale` renders at reduced size for preview (contract: equal to scale-1 output resized, ±1 per channel)
- [X] T015 Create `musclereels/video.py`: `VideoInfo`, `VideoSource(path)` with ffprobe probing (fallback: parse `ffmpeg -i` output), `needs_proxy` when `avg_frame_rate ≠ r_frame_rate` or rotation not applied by OpenCV, `prepare(progress_cb)` writes a CFR proxy to `.musclereels-cache/<hash>.mp4` next to the input, `frame_at(t)` (seek to earlier keyframe via `CAP_PROP_POS_MSEC` then decode forward), `iter_frames(t0, t1)`; move `fit_frame` here (re-export from `render.py`)
- [X] T016 Update `require_ffmpeg()` in `musclereels/render.py` to prefer `PATH` ffmpeg, then `imageio_ffmpeg.get_ffmpeg_exe()` if installed, else the existing install message
- [X] T017 Rewrite `musclereels/project.py` for edit script v2 per contracts/edit-script-v2.md: `Project`, `Segment` (+ `overrides`, `layout`, `insets` fields), `load_project` (v1 migration: `position` → `card-<position>`, bool `trim` kept), `save_project` (always `version: 2`, relative paths), strict key validation raising `ProjectError(file, line, message)`; keep `load_job` as a wrapper returning the old `Job` shape until callers are migrated
- [X] T018 Update `musclereels/render.py` to take a `Project`: use `VideoSource`, `effective_layout` per segment, `build_sprites`; add `progress_cb(fraction)` and `cancel: threading.Event`; on cancel kill ffmpeg, delete the partial file, raise `RenderCancelled`; move `envelope` and add `frame_for_time(project, t, scale)` (shared by preview and export)
- [X] T019 Update `musclereels/cli.py` to the new core: `render` loads projects via `load_project`; add `--layout-preset NAME_OR_FILE` (supersedes `--position`, which maps to `card-<pos>`); `list --presets`; exit codes per contracts/cli.md (`2` for validation, `1` for render failures)
- [X] T020 Run the full suite; T006–T010 and the existing `tests/test_core.py` pass

**Checkpoint**: core is element-based, v2-capable and cancellable; 001 output is unchanged.

---

## Phase 3: User Story 1 – Build a reel visually (Priority: P1) 🎯 MVP

**Goal**: open a clip in the app, pick an exercise, preview in 9:16, export, save/open projects.

**Independent Test**: a non-CLI user loads a clip, picks "Squat", exports, and the file uploads to Instagram unedited (quickstart §4 steps 1, 2, 8).

### Tests (write first, must fail)

- [X] T021 [P] [US1] Write `tests/test_parity.py`: for a project with 2 segments, `frame_for_time(project, t, scale=1.0)` matches the frame decoded from `render()` output at t ∈ {0.4, 1.0, 2.5}: luma PSNR ≥ 40 dB and clearly better than the neighbouring frames (H.264 4:2:0 chroma alone costs ~31 dB on the test pattern, so a per-pixel bound isn't meaningful)
- [X] T022 [P] [US1] Write `tests/app/test_open_export.py` (pytest-qt): launch `MainWindow`, open `demo_clip`, select "rdl" in the exercise panel → segment created covering the clip with "Romanian Deadlift"; play for 0.5 s without errors; export to tmp via the export dialog; output is 1080×1920 h264 with audio; Save then reopen → identical `Project`
- [X] T023 [P] [US1] Write `tests/app/test_errors.py`: opening a text file renamed `.mp4` shows an error dialog and the window remains usable; `musclereels app` without PySide6 importable exits 2 with the `pip install "musclereels[app]"` message

### Implementation

- [X] T024 [US1] Implement `musclereels/app/__init__.py` `launch(path=None)` creating `QApplication` + `MainWindow`; import guard for PySide6 → friendly message; add `musclereels app [project.yaml|clip.mp4]` subcommand in `musclereels/cli.py`
- [X] T025 [P] [US1] Implement `musclereels/app/player.py`: `Player(QObject)` on a worker `QThread` using `VideoSource.frame_at`/`iter_frames`, LRU cache (≤ ~300 MB, ≈ 150 frames at 540×960), signals `frameReady(t, QImage)`, `positionChanged(t)`; play/pause/seek/step(±1 frame)/jump(±1 s); compositing via `frame_for_time(project, t, scale=0.5)`
- [X] T026 [P] [US1] Implement `musclereels/app/canvas.py`: `QGraphicsView` with fixed 1080×1920 scene scaled to fit; background `QGraphicsPixmapItem` showing frames composited by `frame_for_time` (overlay included, so preview == export; draggable element items arrive in US2 T037/T038); shaded Instagram reserved areas toggle
- [X] T027 [P] [US1] Implement `musclereels/app/exercise_panel.py`: search field filtering `ExerciseDB` by name/alias with `difflib` close matches; click applies to the selected segment or creates one covering the whole clip if none exist; "Custom…" creates a segment with title + empty muscles
- [X] T028 [P] [US1] Implement `musclereels/app/inspector.py` (segment section): title and subtitle fields updating the project and redrawing immediately (FR-004)
- [X] T029 [P] [US1] Implement `musclereels/app/export_dialog.py`: runs `render()` in a `QThread`, progress bar from `progress_cb`, Cancel sets the event, success shows "Show in folder"; failures display the error text
- [X] T030 [US1] Implement `musclereels/app/main_window.py`: toolbar (Open, Save, Save As, Export), drag-and-drop of video/project files, panel layout per contracts/ui.md, keyboard shortcuts (Space, ←/→, Shift+←/→), state machine Empty → Editing(clean/dirty) → Exporting, unsaved-changes prompt on close, window title with `*` when dirty; while a clip loads that `needs_proxy`, show a progress dialog for `VideoSource.prepare`
- [X] T031 [US1] Wire save/open to `save_project`/`load_project`; opening a v1 script works; validation errors from `ProjectError` shown with file:line
- [X] T032 [US1] Run T021–T023 green; manually run quickstart §4 steps 1, 2, 8

**Checkpoint**: MVP: a reel can be made end to end in the app (fixed `card-left` layout).

---

## Phase 4: User Story 2 – Place the front and back figures freely (Priority: P1)

**Goal**: drag/resize/hide figures, legend and title independently; safe-zone snapping; presets; per-segment overrides; undo/redo.

**Independent Test**: show only the back figure, large, bottom-left above the caption area; export matches the preview (quickstart §4 steps 3–4).

### Tests (write first, must fail)

- [X] T033 [P] [US2] Write `tests/app/test_layout_editing.py`: drag the back figure item by (−300, +400) → project layout updated; release inside the bottom reserved area → snapped to y + height ≤ 1470; Alt-drag keeps it outside and sets `allow_outside_safe_zone: true`; corner-resize keeps aspect; hide front → not in exported frame; Ctrl+Z restores each step, Ctrl+Shift+Z redoes
- [ ] T034 [P] [US2] Write `tests/app/test_presets.py`: save current layout as "back-big" → YAML in the config dir (tmp via `QStandardPaths.setTestModeEnabled(True)`); apply it in a new project; delete it; built-ins can't be deleted
- [ ] T035 [P] [US2] Write `tests/app/test_segment_override.py`: with 2 segments, "This segment only" then moving the front figure changes only segment 2's `layout` override; segment 1 keeps the default

### Implementation

- [X] T036 [US2] Undo/redo (FR-008): one `QUndoStack` in `musclereels/app/main_window.py` with toolbar Undo/Redo; every edit (exercise, text, visibility, panel style, opacity, move, resize) is recorded as a whole-project snapshot command (`_Snapshot`), consecutive opacity-slider moves merge into one step
- [X] T037 [US2] Implement `musclereels/app/figure_item.py`: `ElementItem(QGraphicsPixmapItem)` movable with 4 corner handles (aspect locked), live pixmap scaling during resize then debounced (100 ms) re-raster via `build_sprites` for that element only; on release call `snap_to_safe_zone` unless Alt held; push commands from T036
- [X] T038 [US2] Make `canvas.py` items editable: replace static sprites with `ElementItem`s for title/front/back/legend; selection outline; reserved areas shown while dragging; minimum-size warning when a figure width < 120 px
- [X] T039 [P] [US2] Add Overlay section in `musclereels/app/inspector.py`: checkboxes for Title text, Muscle names, FRONT/BACK labels, Front figure, Back figure; Panel combo (`grouped`/`per_element`/`none`); panel Opacity slider 0–100 % (FR-010a)
- [ ] T040 [P] [US2] Implement `musclereels/app/presets_store.py` and toolbar "Preset ▾" menu: list built-ins + user presets from `QStandardPaths.AppConfigLocation/presets/*.yaml`, Save current…, Delete (user only), apply via `ApplyPreset`
- [ ] T041 [US2] Add right-click menu "This segment only" / "Reset to project default" on `ElementItem`s; edits while active write a `SegmentLayoutOverride` on the selected segment
- [ ] T042 [US2] Run T033–T035 green and quickstart §4 steps 3–4

**Checkpoint**: layout is fully flexible and undoable; US1 still passes.

---

## Phase 5: User Story 4 – Show specific muscles (Priority: P1)

**Goal**: Detailed level with 40 muscles from one SVG source; exercise remap; hover names; click to cycle primary → secondary → off.

**Independent Test**: "Incline Bench Press" at Detailed → only `upper_chest` primary, legend "Upper Chest" (quickstart §3).

### Tests (write first, must fail)

- [ ] T043 [P] [US4] Write `tests/test_muscles.py`: exactly 40 detailed muscles; each has exactly one parent among the 18 groups with the table in data-model.md (e.g. `sternocleidomastoid`→`traps`, `serratus_anterior`→`obliques`, `hip_flexors`→`quads`, `tibialis_anterior`→`calves`, `infraspinatus`→`rhomboids`, `teres_major`→`lats`); every muscle has polygons in each listed view; `short_name` ≤ 16 chars; resolving `chest` yields `upper_chest, mid_chest, lower_chest`
- [ ] T044 [P] [US4] Write `tests/test_activation.py`: Detailed: `incline_bench_press` → `{upper_chest: primary, anterior_delt: primary, triceps_*: secondary}` and `mid_chest`/`lower_chest` absent; group in primary + its muscle in secondary → the specific muscle's list wins for that muscle; Simple level from detailed activation: group primary if any muscle primary; segment `overrides` applied last (`off` removes)
- [ ] T045 [P] [US4] Write `tests/test_hit_test.py`: `BodyMap.hit_test('front', x, y, 'detailed')` returns `upper_chest` at the upper-chest centroid, `None` outside the body; at `simple` returns `chest`; mirrored left/right sides both hit
- [ ] T046 [P] [US4] Write golden tests `tests/golden/test_golden.py`: render front/back at Detailed and Simple for `incline_bench_press`, `lateral_raise`, `hammer_curl`, `bulgarian_split_squat` at width 420 and compare with `tests/golden/*.png` (tolerance: mean abs diff < 1.0); `--update-golden` rewrites them
- [ ] T047 [P] [US4] Write `tests/app/test_muscle_clicks.py`: hover over upper chest shows tooltip with `full_name`; click cycles primary → secondary → off on the selected segment (`overrides` updated, legend redraws); undo restores; Detail toggle redraws figures

### Implementation

- [ ] T048 [US4] Draw `assets/bodymap.svg` (200×440 design space per view, `<g id="front">`, `<g id="back">`, one `<path id="<muscle_id>">` per right-side region, plus filler shapes `filler-*`), keeping the current silhouette; all 40 muscle ids from data-model.md
- [ ] T049 [US4] Write `tools/build_bodymap.py`: parse `assets/bodymap.svg` with svgelements, flatten curves (tolerance 0.5 design units), mirror right→left, write `musclereels/data/bodymap/front.json` and `back.json` (`{fillers: [...], regions: {id: [[x,y],...]}}`); fail if any id in `muscles.yaml` lacks a region in a listed view; commit generated JSON
- [ ] T050 [US4] Extend `musclereels/data/muscles.yaml` with the 40 detailed muscles: `id`, `short_name` (≤ 16 chars), `full_name`, `group`, `views`, exactly per data-model.md
- [ ] T051 [US4] Refactor `musclereels/bodymap.py` into `BodyMap` loading the JSON art: `render(view, activation, width_px, theme, level, glow)` with Chaikin smoothing (2 iterations) and Simple level drawn by merging regions per group; `hit_test(view, x, y, level)` (point-in-polygon, reverse draw order); remove the inline polygon lists; keep `render_figure` as a wrapper for compatibility
- [ ] T052 [US4] Implement activation in `musclereels/project.py` (`Project.activation(segment, level)`) and MuscleRef support in `musclereels/exercises.py`: refs may be groups, muscles or aliases; precedence rules from data-model.md "Exercise"
- [ ] T053 [US4] Update legend in `musclereels/overlay.py`: Detailed names use `short_name`; when > 6 chips, group by parent ("Chest: Upper, Mid"); Simple label "Traps & Neck" only when `sternocleidomastoid` is lit, "Lower Leg" when `tibialis_anterior` is lit
- [ ] T054 [US4] Remap `musclereels/data/exercises.yaml` to detailed muscles where consensus is clear (incline press → `upper_chest`; hammer curl → `brachialis`, `brachioradialis`; lateral raise → `lateral_delt`; Bulgarian split squat → `gluteus_medius` secondary; RDL → `medial_hamstrings`, `biceps_femoris`; shrug → `upper_traps`; face pull → `posterior_delt`, `infraspinatus`; calf raise → `gastrocnemius`, `soleus` …), keeping group refs elsewhere; one-line rationale comment per change (Constitution III)
- [ ] T055 [US4] CLI: `--detail {simple,detailed}` on `render`/`preview`; `list --muscles --detailed` prints id, short name, full name, group (`musclereels/cli.py`)
- [ ] T056 [US4] App: Detail toggle in the toolbar (undoable `SetDetailLevel`); in `figure_item.py` map scene coords → design coords, hover tooltip via `hit_test` + `full_name`, click pushes `SetMuscleOverride` cycling primary → secondary → off; muscle chips in the inspector mirror the selection
- [ ] T057 [US4] Regenerate goldens, review them visually, run T043–T047 green and quickstart §3

**Checkpoint**: Detailed map works in CLI and app; Simple output unchanged (T006 still green).

---

## Phase 6: User Story 3 – Several exercises on a timeline (Priority: P2)

**Goal**: create/move/resize/delete segments and trim on a timeline.

**Independent Test**: three segments made by dragging; each overlay only appears in its range (quickstart §4 step 5).

### Tests (write first, must fail)

- [ ] T058 [P] [US3] Write `tests/app/test_timeline.py`: Shift-drag creates a segment; dragging an edge into a neighbour is clamped (no overlap); `S` splits at the playhead; Delete removes the selected segment; trim handles set `trim.in/out` and export duration matches; all undoable
- [ ] T059 [P] [US3] Write `tests/test_short_segment.py`: a 0.5 s segment uses shortened fades (each ≤ 25 % of segment length) and reaches opacity 1.0 at its midpoint

### Implementation

- [ ] T060 [US3] Implement `musclereels/app/timeline.py`: custom `QWidget` painting clip duration, segment blocks (labelled with titles), playhead, trim handles; interactions per contracts/ui.md (Shift-drag new, drag edges/move, `S` split, Delete); clicks seek the player; every edit pushes commands from T036
- [ ] T061 [US3] Update `envelope()` in `musclereels/render.py` so fade duration = min(0.35 s, 25 % of segment length) (spec edge case: very short segment)
- [ ] T062 [US3] Wire timeline selection ↔ inspector ↔ exercise panel in `musclereels/app/main_window.py` (selected segment is the edit target)
- [ ] T063 [US3] Run T058–T059 green and quickstart §4 step 5

**Checkpoint**: multi-exercise reels can be built without YAML.

---

## Phase 7: User Story 5 – Zoom in on a muscle (Priority: P2)

**Goal**: detail insets (region or auto) with labels and zoom entrance, placed like figures.

**Independent Test**: "Shoulder" inset for Lateral Raise top-right; side delt clearly visible and labelled in the export (quickstart §3, §4 step 7).

### Tests (write first, must fail)

- [ ] T064 [P] [US5] Write `tests/test_inset.py`: `region_box('shoulder', 'front', …)` is inside the figure bounds; `auto` for `lateral_raise` = bounding box of primary polygons padded 15 % with aspect clamped to 3:4…4:3; `view: auto` picks the view with the most primary area; inset sprite with `labels: true` contains callout text for each lit muscle in the box; `entrance: zoom` at t = segment start + 0.1 s is between the full-figure box and the final box
- [ ] T065 [P] [US5] Write `tests/app/test_insets.py`: "Insets → + Add" creates an auto inset on the selected segment; it moves/resizes/snaps like figures; toggling labels and removing it are undoable; the exported frame contains it
- [ ] T066 [P] [US5] Add golden images for insets (`lateral_raise` shoulder, `hammer_curl` arm, labels on) to `tests/golden/test_golden.py`

### Implementation

- [ ] T067 [US5] Add `musclereels/data/bodymap/regions.json` with design-space boxes for `shoulder, chest, arm, forearm, core, back, hip, thigh, lower_leg` per view; implement `BodyMap.region_box` (incl. `auto`) in `musclereels/bodymap.py`
- [ ] T068 [US5] Implement `musclereels/inset.py`: render the figure at the zoom scale for the box (smoothing makes edges clean), rounded-panel crop, optional callouts (leader line from region centroid to label using `full_name`, placed to avoid overlap), entrance `fade` | `zoom` (interpolate from full-figure box to final placement over 0.5 s)
- [ ] T069 [US5] Add `DetailInset(region, view, placement, labels, entrance)` to `musclereels/project.py` with validation of enum values from data-model.md (`region` ∈ {auto, shoulder, chest, arm, forearm, core, back, hip, thigh, lower_leg}; `view` ∈ {front, back, auto}; `entrance` ∈ {fade, zoom}); include insets in `build_sprites` (`musclereels/overlay.py`)
- [ ] T070 [US5] CLI `--inset REGION` for quick `render`/`preview`; `list --regions` (`musclereels/cli.py`)
- [ ] T071 [US5] App: Insets section in `musclereels/app/inspector.py` (+ Add, region combo, view, labels, entrance, remove) and inset `ElementItem`s on the canvas reusing `figure_item.py`; commands `AddInset`, `EditInset`, `RemoveInset`
- [ ] T072 [US5] Run T064–T066 green and quickstart §4 step 7

**Checkpoint**: all five stories work independently.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T073 [P] Implement `musclereels/app/autosave.py` (every 30 s when dirty → `<project>.autosave.yaml` or app-data file for unsaved projects; recovery prompt on launch; delete on clean save/exit) with test `tests/app/test_autosave.py` (FR-007)
- [ ] T074 [P] Performance check script `tools/bench_preview.py`: measure preview fps at 540×960 on a 1080p clip (target ≥ 24), element re-raster time (target < 50 ms), export speed (≤ 3× real time); record results in `specs/002-editor-ui-detailed-muscles/quickstart.md`
- [ ] T075 [P] Packaging: `packaging/musclereels.spec` (PyInstaller one-folder, bundles data files and imageio-ffmpeg binary, ffmpeg license file) and `.github/workflows/build-app.yml` producing a Windows zip and macOS `.dmg` as artifacts
- [ ] T076 [P] Update `README.md`: app install/launch, screenshots of the editor and detailed figures (from goldens), Detailed muscles list, edit script v2, presets, insets; update `examples/session.yaml` to v2 and add `examples/session_v1.yaml` for compatibility
- [ ] T077 [P] Update `specs/001-reel-rendering/spec.md` "Status" note to reference 002 for layout/detail additions (no behaviour change)
- [ ] T078 Run the complete `quickstart.md` validation (all sections) on Windows and macOS builds; fix issues found
- [ ] T079 Final: `pytest` green on the CI matrix, golden images reviewed in the PR, open PR `002-editor-ui-detailed-muscles` → `main`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none
- **Foundational (Phase 2)**: needs Setup; **blocks all stories**
- **US1 (Phase 3)**: needs Foundational
- **US2 (Phase 4)**: needs US1 (canvas, main window, commands host)
- **US4 (Phase 5)**: core part (T043–T046, T048–T055) needs only Foundational and can run **in parallel with US1/US2**; app part (T047, T056) needs US1 + T036/T037 from US2
- **US3 (Phase 6)**: needs US1 and T036 (commands)
- **US5 (Phase 7)**: needs US4 core (detailed art, `region_box`) and, for the app part, US2's `ElementItem`
- **Polish (Phase 8)**: after the stories to be shipped

```
Setup → Foundational ─┬─ US1 ─ US2 ─┬─ US3
                      │             ├─ US4-app ─┐
                      └─ US4-core ──┴───────────┴─ US5 → Polish
```

### Within each story

Tests first (must fail) → core/data → CLI → app → story validation task.

### Parallel opportunities

- Setup: T002–T005 together.
- Foundational tests T006–T010 together; then T011, T012, T015, T016 in parallel (different files), followed by T013 → T014 → T017 → T018 → T019.
- US1: T025, T026, T027, T028, T029 together after T024; T030 integrates them.
- US2: T039 and T040 in parallel with T037/T038.
- US4: drawing the art (T048) can start on day 1 alongside Foundational; T043–T046 together.
- US3 and US5 core (T064, T066–T070) can proceed in parallel once their dependencies are met.

### Parallel example: User Story 4 (core)

```text
Task: "T043 Write tests/test_muscles.py"
Task: "T044 Write tests/test_activation.py"
Task: "T045 Write tests/test_hit_test.py"
Task: "T046 Write golden tests tests/golden/test_golden.py"
then
Task: "T048 Draw assets/bodymap.svg"   (in parallel with)   Task: "T050 Extend musclereels/data/muscles.yaml"
```

## Implementation Strategy

### MVP first (US1)

1. Phase 1 Setup → Phase 2 Foundational (001 output proven unchanged by T006).
2. Phase 3 US1 → **stop and validate**: make a real reel in the app with the fixed card layout.
3. Tag `v0.2.0-alpha1`.

### Incremental delivery

1. + US2 → flexible figures (the headline request) → `alpha2`.
2. + US4 → detailed muscles (core can land earlier for CLI users) → `beta1`.
3. + US3 timeline → + US5 insets → Polish/packaging → `v0.2.0`.

Each increment keeps all earlier stories' tests green.

## Notes

- 79 tasks; `[P]` = different files with no unfinished dependencies.
- Commit after each task or logical group; never weaken the T006 compatibility test to make it pass.
- Golden image changes must be reviewed visually in the PR (Constitution V).
