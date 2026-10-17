# Contract: Core API used by the app

The app (`musclereels.app`) may only use these core entry points, so that it stays a thin layer
(Constitution IV) and everything it can render the CLI can render too.

```python
# musclereels.muscles
registry() -> MuscleRegistry
MuscleRegistry.resolve(refs: list[str]) -> list[str]                  # → muscle ids
MuscleRegistry.group_of(muscle_id) -> str
MuscleRegistry.muscles(level: "simple"|"detailed") -> list[Muscle]

# musclereels.bodymap
BodyMap.render(view, activation, width_px, theme, level, glow=1.0) -> PIL.Image   # RGBA
BodyMap.hit_test(view, x_design, y_design, level) -> str | None                    # muscle or group id
BodyMap.region_box(region, view, activation) -> (x0, y0, x1, y1)                   # design space

# musclereels.project
load_project(path) -> Project          # v1 or v2; raises ProjectError(file, line, message)
save_project(project, path) -> None    # always v2
Project.validate() -> None
Project.activation(segment, level) -> dict[str, "primary"|"secondary"]

# musclereels.layout
builtin_presets() -> dict[str, Layout]
load_preset(path) / save_preset(preset, path)
effective_layout(project, segment) -> Layout                          # default + override
snap_to_safe_zone(placement, element_size) -> ElementPlacement

# musclereels.overlay
build_sprites(project, segment, layout, scale=1.0) -> list[Sprite]    # scale 0.5 for preview
composite(frame_bgr, sprites, glow, opacity) -> None                  # in place
envelope(t, segment, pulse_hz) -> (glow, opacity)

# musclereels.video
VideoSource(path).info -> VideoInfo(duration, fps, size, has_audio, needs_proxy)
VideoSource.prepare(progress_cb) -> None                             # builds CFR proxy if needed
VideoSource.frame_at(t: float) -> np.ndarray                          # BGR, exact frame
fit_frame(frame, mode, out_size=(1080, 1920)) -> np.ndarray

# musclereels.render
render(project, progress_cb=None, cancel: threading.Event=None) -> Path
```

Guarantees:
- `build_sprites(..., scale=s)` returns the same pixels as `scale=1.0` resized by `s` within ±1 per channel (used by the preview).
- The same `Project` given to `render()` and previewed at full scale at time `t` gives pixel-identical frames (parity test).
- None of these functions import Qt.
