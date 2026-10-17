# Contract: CLI changes

Every 001 command and flag keeps working unchanged. Additions:

| Command / flag | Behaviour |
|---|---|
| `musclereels app [project.yaml \| clip.mp4]` | Launch the editor, optionally opening a project or clip. If the `app` extra is not installed: exit 2 with `pip install "musclereels[app]"`. |
| `render … --detail {simple,detailed}` | Detail level for quick mode; overrides the script's `detail_level`. |
| `render … --layout-preset NAME_OR_FILE` | Built-in preset name or a preset YAML file. Supersedes `--position`. |
| `render … --inset REGION` | Quick mode: add one inset (`auto`, `shoulder`, …) with labels. |
| `preview …` | Accepts `--detail`, `--layout-preset`, `--inset`. |
| `list --muscles [--detailed]` | `--detailed` lists the 40 muscles with full names and parent group. |
| `list --presets` | Built-in and user layout presets. |
| `list --regions` | Inset regions. |

Exit codes: `0` ok; `1` render/ffmpeg failure; `2` usage/validation error (bad script, unknown muscle/exercise/key, missing extra).
Errors go to stderr as `error: <message>`; validation errors include `file:line` when known.
