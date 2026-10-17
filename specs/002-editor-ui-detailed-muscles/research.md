# Research: Reel Editor App with Detailed Muscle Map

Decisions behind [plan.md](plan.md). Each entry lists the decision, why, and what else was considered.

## R1. UI toolkit

**Decision**: PySide6 (Qt 6), with the editor canvas built on `QGraphicsView`/`QGraphicsScene`.

**Rationale**
- Same language as the core, so the app calls the existing render code directly. That is what makes "preview == export" (SC-004) achievable without two renderers.
- `QGraphicsScene` gives drag, resize handles, z-order, hit testing and zoom out of the box, which covers most of Story 2.
- `QUndoStack` covers FR-008 (undo/redo).
- Native look and file dialogs on Windows and macOS. LGPL license, fine with dynamic linking in a one-folder bundle.

**Alternatives considered**
- *Electron/Tauri + web UI + Python sidecar*: nicer UI tooling, but two languages, IPC for every frame, and the overlay would be drawn twice (canvas and Python), which risks preview/export drift. Too much complexity for one developer.
- *Local web UI (FastAPI + browser)*: no GUI dependency, but scrubbing video through a local server is laggy, and "open the app" becomes "start a server and open a tab".
- *Tkinter*: no real canvas transforms, poor video performance, dated look.
- *Dear PyGui*: fast, but immature text/layout and weak native dialogs.

## R2. Keeping preview identical to export

**Decision**: one renderer. The core rasterises every overlay element (title, front figure, back figure, legend, insets) into RGBA sprites. The app shows those same sprites as `QGraphicsPixmapItem`s over the video frame. Export composites the same sprites with the same `composite()` call.

- Dragging moves a pixmap: instant, no re-render.
- Resizing re-rasterises only that element at the new size (target < 50 ms), debounced while the handle is held, with a scaled pixmap shown meanwhile.
- Fade/pulse in the preview use the same `envelope()` function as export.
- Preview runs at half resolution (540×960) for speed; export is 1080×1920. Element geometry is stored in canvas pixels (1080×1920), so both scale from one source.
- A test renders frame *t* via the preview path at full resolution and via the export path, and requires a pixel-identical result.

**Alternatives considered**: drawing figures as Qt vector items in the app (sharper while zoomed, but a second renderer that will drift from the export).

## R3. Video decoding, seeking and variable frame rate

**Decision**: keep OpenCV for decoding in both app and export, behind a small `VideoSource` class. On load, `ffprobe` checks the clip:
- **VFR** (common on phones: `avg_frame_rate` ≠ `r_frame_rate`) or **rotation metadata** that OpenCV doesn't apply → make a constant-frame-rate *proxy* once with ffmpeg (`-vf fps=…`, rotation baked in), cached next to the project in `.musclereels-cache/`. App and export both read the proxy.
- Seeking: jump to the nearest earlier keyframe with `CAP_PROP_POS_MSEC`, then decode forward to the exact frame. A small LRU cache of decoded frames around the playhead makes stepping and scrubbing smooth.
- Playback runs on a worker `QThread` that delivers frames timed to an audio-less clock (QtMultimedia audio playback in the preview is a stretch goal).

**Rationale**: a single decoder for preview and export keeps them identical, and the proxy approach fixes VFR and rotation without adding PyAV (~60 MB) to the core path (Constitution VI).

**Alternatives considered**
- *PyAV everywhere*: accurate PTS and seeking, but a heavy new core dependency.
- *QtMultimedia for preview playback*: smooth, with audio, but it's a different decoder than the export (timing/orientation mismatches) and gives no access to frames for compositing.

## R4. ffmpeg for app users

**Decision**: the app extra depends on `imageio-ffmpeg`, which ships a static ffmpeg binary as a wheel. `require_ffmpeg()` prefers ffmpeg on `PATH`, falls back to `imageio_ffmpeg.get_ffmpeg_exe()`. ffprobe isn't in that wheel, so probing uses `ffmpeg -i` output parsing as the fallback.

**Rationale**: the spec assumes everyday use without a terminal; users shouldn't have to install ffmpeg separately.

**Note**: the bundled ffmpeg includes GPL components (libx264). It runs as a separate executable (aggregation, not linking). The bundle ships the ffmpeg license and a source link.

## R5. Detailed muscle art: authoring and storage

**Decision**
- Source of truth: `assets/bodymap.svg`, with one `<path id="…">` per muscle region in front and back groups, drawn in a vector editor (Inkscape) over the existing figure silhouette. Left-side shapes are mirrored automatically, as today.
- A dev script (`tools/build_bodymap.py`, dev-only dependency `svgelements`) flattens the paths into polygons and writes `musclereels/data/bodymap/{front,back}.json`, which are committed.
- At runtime, only JSON is read; there is no SVG dependency. Polygons are smoothed with Chaikin subdivision at render time, so edges stay smooth when an inset enlarges them 3–4×.
- Simple level is derived from the same art by merging muscles by parent group, so there is one drawing, not two.

**Rationale**: drawing 40 muscles by typing coordinates (how the 001 figures were made) doesn't scale. An SVG can be edited visually and reviewed as an image in PRs (Constitution V). Keeping runtime data as JSON keeps Constitution IV/VI.

**Alternatives considered**: hand-written polygons in Python (current; unmaintainable at 40 regions); loading SVG at runtime (needs `cairosvg`/Qt SVG in the core); licensed anatomy illustrations (cost, licensing, and a realistic style the spec rules out).

## R6. Parent groups for muscles outside the 18 Simple groups

FR-019 requires every detailed muscle to belong to exactly one of 001's 18 groups. Four don't fit naturally. Decisions (under-claiming, per Constitution III):

| Detailed muscle | Parent group | Reason |
|---|---|---|
| Sternocleidomastoid (neck) | `traps` | Shares the neck/upper-shoulder area on the simple figure; simple label becomes "Traps & Neck" only when the neck is lit. |
| Serratus anterior | `obliques` | Sits on the side of the ribcage where the simple obliques shape is drawn. |
| Hip flexors | `quads` | Rectus femoris is itself a hip flexor; the region sits at the top of the thigh. |
| Tibialis anterior | `calves` | Simple map treats the lower leg as one group; legend shows "Lower Leg" when the tibialis is lit. |
| Infraspinatus, teres major | `rhomboids` / `lats` | Scapular area → upper back; teres major works with the lats. |
| Brachialis / brachioradialis | `biceps` / `forearms` | Standard grouping in gym content. |

## R7. Hit testing (click/hover a muscle)

**Decision**: point-in-polygon in design space (200×440), done in the core (`BodyMap.hit_test(view, x, y)`), checking regions in reverse draw order. The app maps scene coordinates into the figure's design space. 40 regions × ~30 vertices is trivially fast.

## R8. Layout model and the old card

**Decision**: the overlay becomes independent **elements** (`title`, `front`, `back`, `legend`, `insets[]`), each with visibility and a box in canvas pixels (x, y, width; height follows the element's aspect). Backgrounds have a `card` mode:
- `grouped`: one rounded panel around the visible figures and legend (this reproduces the 001 look);
- `per_element`: a panel behind each element;
- `none`.

The 001 positions `left`/`right`/`center` become built-in layout presets computed by the same code as today's card, so 001 scripts render the same (SC-005). Safe-zone snapping clamps an element's box into the safe rectangle on release; `allow_outside_safe_zone: true` per element is the explicit override (FR-011).

## R9. Project file format

**Decision**: extend the YAML edit script with `version: 2`. Files without `version` are read as v1 and mapped to v2 in memory (`position` → preset layout, simple muscle names unchanged). The app always saves v2. The CLI reads both. Unknown keys raise a clear error naming the key, so typos are caught. Schema: [contracts/edit-script-v2.md](contracts/edit-script-v2.md).

Layout presets are stored as small YAML files in the user config directory (`QStandardPaths.AppConfigLocation` from the app; the CLI accepts `--layout-preset path.yaml`).

## R10. Autosave and recovery

**Decision**: every 30 s and on each export, if the project is dirty, write `<project>.autosave.yaml` (or, for unsaved projects, a file in the app data dir). On launch, a newer autosave than its project triggers a "Recover unsaved changes?" prompt. Clean saves and exits delete the autosave.

## R11. Testing approach

- **Unit (pytest)**: muscle registry and parent mapping, exercise resolution with groups and sub-muscles, layout snapping, v1→v2 migration and round-trip, hit testing, inset framing.
- **Golden images**: figures, legend and insets rendered at fixed size and compared with stored PNGs (small tolerance), regenerated deliberately with `pytest --update-golden`. The PNGs double as PR previews (Constitution V).
- **Parity test**: preview path vs export path pixel equality (R2).
- **App (pytest-qt, `QT_QPA_PLATFORM=offscreen`)**: open a sample clip, pick an exercise, drag a figure, undo, save, reload, export a 2-second clip.
- **CI**: GitHub Actions matrix (ubuntu, windows, macos) for tests; app bundles built on windows and macos.

## R12. Packaging

**Decision**: PyInstaller one-folder builds produced by GitHub Actions for Windows (zip, later an installer) and macOS (`.app` in a `.dmg`, unsigned at first, so users must allow it in macOS security settings). Developers can still run `pip install -e ".[app]"` and `musclereels app`.

**Alternatives considered**: Briefcase (cleaner installers, less mature with PySide6 + OpenCV); Nuitka (slower builds, harder CI).
