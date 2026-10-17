# Quickstart: validate feature 002

Run-through proving the feature works end to end. Each step references the spec story it validates.

## Prerequisites

```bash
git checkout 002-editor-ui-detailed-muscles
pip install -e ".[app,dev]"        # PySide6, imageio-ffmpeg, pytest-qt
musclereels demo                   # creates demo/demo_clip.mp4 for the steps below
```

## 1. Automated checks

```bash
pytest                                   # unit, golden-image, parity, migration tests
QT_QPA_PLATFORM=offscreen pytest tests/app   # app smoke tests (Windows: set QT_QPA_PLATFORM=offscreen)
```
Expected: all pass. Golden PNGs in `tests/golden/` show the detailed figures, legend and insets.

## 2. Backwards compatibility (SC-005)

```bash
git stash -u; git checkout main && musclereels render examples/session.yaml -o out/v1.mp4; git checkout -; git stash pop
musclereels render examples/session.yaml -o out/v2.mp4
python tools/compare_videos.py out/v1.mp4 out/v2.mp4     # expect: identical frames
```

## 3. Detailed muscles from the CLI (Story 4)

```bash
musclereels list --muscles --detailed                    # 40 muscles with parent groups
musclereels preview -e incline_bench_press --detail detailed -o out/incline.png
musclereels preview -e lateral_raise --detail detailed --inset auto -o out/lateral.png
```
Expected: in `incline.png`, only the upper chest is red, legend says "Upper Chest". In `lateral.png`, the side delt is red with an enlarged, labelled shoulder inset.

## 4. App walkthrough (Stories 1–3, 5)

```bash
musclereels app demo/demo_clip.mp4
```
1. Search "rdl" → Romanian Deadlift appears on both figures. *(Story 1)*
2. Press Space: overlay fades in and pulses as in the export. *(Story 1)*
3. Hide the front figure; drag the back figure to the bottom-left and enlarge it; drag it into the caption area and release, so it snaps back above it. *(Story 2)*
4. Save the layout as preset "back-big"; start a new project and apply it. *(Story 2)*
5. Shift-drag on the timeline to make 3 segments with different exercises; try to overlap two (refused). *(Story 3)*
6. Switch to Detailed; click the upper chest on segment 1 to cycle it. Undo it. *(Story 4)*
7. Add an inset (auto, labels, zoom entrance) to segment 2. *(Story 5)*
8. Save as `out/session2.yaml`, export to `out/app.mp4`, cancel once mid-way, then export again fully. *(Story 1)*
9. `musclereels render out/session2.yaml -o out/cli.mp4` and compare with `out/app.mp4`: identical. *(SC-004)*
10. Edit something, force-quit the app, relaunch: recovery prompt restores the edit. *(FR-007)*

## 5. Platforms (FR-027)

Repeat step 4 with the packaged app from the CI artifacts on Windows 10+ and macOS 12+.
