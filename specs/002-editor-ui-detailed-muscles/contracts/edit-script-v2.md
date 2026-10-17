# Contract: Edit Script v2 (project file)

Shared by the CLI (`musclereels render project.yaml`) and the app (Open/Save). Entities: [data-model.md](../data-model.md).

## Compatibility rules

1. A file without `version` is **v1** (spec 001). It loads unchanged and renders identically at `detail_level: simple`.
2. The app always writes `version: 2`. The CLI reads v1 and v2.
3. Unknown top-level or segment keys are an error that names the key and line.
4. Coordinates are canvas pixels (1080×1920). Paths are relative to the project file.
5. A layout is in one of two modes. **card** (`card-left/right/center` presets, or `{mode: card, position: left}`):
   the v0.1 look, with geometry computed from the content per segment; only `visible` and `labels` apply.
   **free** (any object without `mode: card`): every element has its own box. Moving an element of a
   card layout (in the app or via a segment override with `x`/`y`/`width`) converts it to an
   equivalent free layout first. In free mode, elements are kept inside the safe zone at render time
   using their real size, unless `allow_outside_safe_zone: true`.

## Example

```yaml
version: 2
input: ../clips/upper_day.mp4
output: ../out/upper_day_reel.mp4
trim: { in: "0:02", out: "0:41" }
detail_level: detailed            # simple | detailed

layout:                           # or: layout: card-left   (preset name)
  card: per_element               # grouped | per_element | none
  labels: false
  title:  { visible: true, x: 60,  y: 250, width: 960 }
  front:  { visible: true, x: 60,  y: 980, width: 230 }
  back:   { visible: true, x: 800, y: 420, width: 200 }
  legend: { visible: true, x: 60,  y: 1380, width: 600 }

segments:
  - start: 0
    end: 12
    exercise: incline_bench_press
    subtitle: "4 x 8 @ 70kg"
    insets:
      - region: auto
        labels: true
        entrance: zoom
        placement: { x: 640, y: 980, width: 360 }

  - start: 12
    end: 24
    exercise: lateral_raise
    layout:                       # per-segment override: only these fields change
      back: { visible: false }
    overrides:                    # muscle clicks in the app
      upper_traps: secondary

  - start: 24
    end: end
    title: "Hammer Curl"
    primary: [brachialis, brachioradialis]
    secondary: [biceps_long_head]
```

## Field reference

| Key | Required | Default | Notes |
|---|---|---|---|
| `version` | no | 1 | `2` enables the keys below |
| `input` | yes | | |
| `output` | no | `<input>_reel.mp4` | |
| `trim` | no | none | `{in, out}` or v1 bool |
| `detail_level` | no | `simple` | |
| `layout` | no | `card-left` | object or preset name; preset files via CLI `--layout-preset` |
| `position` | v1 only | | mapped to `card-<position>` |
| `segments[].layout` | no | | partial override |
| `segments[].overrides` | no | `{}` | `muscle_id: primary\|secondary\|off` |
| `segments[].insets[]` | no | `[]` | `region`, `view`, `placement`, `labels`, `entrance` |
| `theme`, `exercises_file`, `pulse_hz`, `crf`, `preset`, `audio`, `card_scale` | no | as 001 | `card_scale` applies to preset layouts only |

## Layout preset file

```yaml
# ~/.config/musclereels/presets/my-corners.yaml (app config dir)
name: my-corners
layout: { card: none, front: { x: 60, y: 1050, width: 240 }, back: { x: 780, y: 420, width: 240 } }
```
