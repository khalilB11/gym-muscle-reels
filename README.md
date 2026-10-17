# 💪 Gym Muscle Reels

A local video tool that turns your gym clips into **Instagram Reels (1080×1920)** with an animated
body map showing which muscles each exercise works — primary muscles glow red, assisting muscles orange.

Everything runs on your machine: no uploads, no accounts.

```
┌──────────────────────┐
│     BENCH PRESS      │  ← exercise title + optional "4 x 8 @ 80kg"
│ ┌────────────┐       │
│ │ FRONT BACK │       │  ← front/back body map, target muscles pulse
│ │  🧍    🧍   │ your  │
│ │ ●Chest     │ clip  │  ← legend chips
│ └────────────┘       │
│                      │  ← bottom kept clear for IG captions
└──────────────────────┘
```

## Features

- **Body map** with 18 muscle groups (front + back), drawn as vectors — sharp at any size
- **36 built-in exercises** (bench, squat, deadlift, rows, curls, …) with aliases like `rdl`, `ohp`, `bss`
- **Multi-exercise edits**: one clip, several segments, each with its own overlay
- **Auto reframing** to 9:16 — crops vertical clips, letterboxes landscape clips on a blurred background
- **Instagram safe zones**: the overlay stays clear of the IG header, caption and buttons
- Fade in/out + pulsing glow, original audio kept, H.264 output ready to upload
- Custom exercises, colors and fonts via YAML

## Install

Requires **Python 3.9+** and **ffmpeg**.

```bash
# ffmpeg
brew install ffmpeg            # macOS
sudo apt install ffmpeg        # Ubuntu/Debian
winget install ffmpeg          # Windows

# the tool
git clone https://github.com/khalilB11/gym-muscle-reels.git
cd gym-muscle-reels
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

musclereels demo               # renders demo/demo_reel.mp4 to check everything works
```

## Usage

**One exercise for the whole clip**

```bash
musclereels render clips/squat.mp4 -e squat --subtitle "5 x 5 @ 120kg"
```

**Only part of the clip, and cut the rest**

```bash
musclereels render clips/set.mp4 -e "hip thrust" --start 0:03 --end 0:12 --trim -o out/hip_thrust.mp4
```

**Several exercises in one reel** — write an edit script ([examples/session.yaml](examples/session.yaml)):

```yaml
input: ../clips/push_day.mp4
output: ../out/push_day_reel.mp4
segments:
  - { start: 0,      end: 7.5,    exercise: bench_press, subtitle: "4 x 8 @ 80kg" }
  - { start: "0:08", end: "0:15", exercise: incline press }
  - { start: 15,     end: end,    title: "Sled Push", primary: [quads, glutes], secondary: [calves] }
```

```bash
musclereels render examples/session.yaml
```

**Check the look without rendering a video**

```bash
musclereels preview -e deadlift -o preview.png
musclereels preview -e deadlift --video clips/dl.mp4 --at 0:04 -o preview.png   # on a real frame
```

**Browse what's available**

```bash
musclereels list             # exercises and their muscles
musclereels list --muscles   # muscle ids and aliases
```

### Options

| Option | Values | Default | |
|---|---|---|---|
| `--position` | `left` `right` `center` | `left` | where the body-map card sits |
| `--fit` | `auto` `cover` `blur` | `auto` | crop to fill vs. letterbox on blurred background |
| `--scale` | e.g. `0.85` | `1.0` | card size |
| `--trim` | flag | off | cut the video to the overlay range |
| `--exercises-file` | path | — | extra YAML with your own exercises |

In YAML you can also set `pulse_hz`, `crf` (quality, lower = better), `preset`, `audio: false` and a `theme`
(colors as hex, `font` as a path to a .ttf for your brand font).

## Custom exercises

```yaml
# my_exercises.yaml
landmine_press:
  name: Landmine Press
  aliases: [landmine]
  primary: [front_delts, chest]
  secondary: [triceps, obliques]
```

```bash
musclereels render clip.mp4 -e landmine --exercises-file my_exercises.yaml
```

Muscle ids: `chest, front_delts, side_delts, rear_delts, traps, rhomboids, lats, lower_back, biceps,
triceps, forearms, abs, obliques, glutes, quads, hamstrings, adductors, calves`
(plus aliases `shoulders, back, core, upper_back, pecs, hams, …`).

## Project layout

```
musclereels/
  bodymap.py       muscle shapes (front/back) and figure rendering
  data/exercises.yaml   exercise → primary/secondary muscles
  exercises.py     exercise database, alias lookup, suggestions
  overlay.py       title + card graphics, safe zones, compositing
  render.py        decode → 9:16 reframe → overlay → ffmpeg encode
  project.py       YAML edit scripts and segments
  cli.py           `musclereels` command
examples/          sample edit script + custom exercises
tests/             pytest suite
```

Tweaking the body art: every muscle is a polygon in a 200×440 design space in `bodymap.py`,
defined for one side and mirrored.

## Roadmap

- [ ] Pose tracking (MediaPipe) to pin muscle highlights onto the athlete's body in the video
- [ ] Auto-detect the exercise and rep counter
- [ ] Desktop GUI with a timeline to mark segments instead of YAML
- [ ] Beat-synced cuts from a music track
- [ ] Caption + hashtag generator per exercise
- [ ] More layouts (split screen, full-body side panel) and themes

## Tests

```bash
pytest
```
