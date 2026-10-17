# Gym Muscle Reels Constitution

## Core Principles

### I. Local-First & Private
All processing runs on the user's machine. No clip, frame, or metadata leaves the device; no
accounts, telemetry, or network calls at render time. Any feature needing a network or cloud
model MUST be opt-in, off by default, and justified in its plan.

### II. Reel-Ready Output
Every render MUST produce a file that uploads to Instagram Reels without re-editing:
1080×1920 (9:16), H.264 + AAC, `yuv420p`, `+faststart`. On-screen graphics MUST stay inside the
Instagram safe zone (top 250 px, bottom 450 px, right 180 px reserved for platform UI).
Original audio is preserved unless the user disables it.

### III. Anatomically Honest
Muscle mappings MUST reflect mainstream exercise-science consensus: *primary* = prime movers,
*secondary* = significant synergists/stabilisers. New or changed exercise entries cite their
reasoning in the PR. When uncertain, under-claim (secondary rather than primary).

### IV. CLI-First, Data-Driven
Every capability is reachable from the `musclereels` CLI and scriptable via YAML edit scripts.
Exercises, muscles, themes and layouts are data (YAML), not code branches. A future GUI MUST be
a thin layer over the same core API.

### V. Test-First (NON-NEGOTIABLE)
Tests are written from the spec's acceptance scenarios before implementation and must fail
first. `pytest` MUST pass on every commit. Visual changes ship with a `musclereels preview`
still (or frame strip) attached to the PR for review.

### VI. Simplicity
Minimal dependencies (currently: OpenCV, NumPy, Pillow, PyYAML, system ffmpeg). Adding a
dependency — especially a heavy one (ML models, GUI toolkits) — requires a justification in the
plan's Complexity Tracking and MUST be an optional extra when not needed by the core render path.

## Technical Constraints

- **Language**: Python ≥ 3.9, cross-platform (macOS, Linux, Windows).
- **Video I/O**: decode with OpenCV, encode by piping raw frames into system `ffmpeg`.
- **Performance**: a 60 s 1080p clip renders in ≤ 3× real time on a typical laptop CPU; no GPU
  required. Memory stays bounded (no whole-video buffering).
- **Determinism**: same input + script + version ⇒ visually identical output.
- **Backwards compatibility**: existing YAML edit scripts and exercise files keep working across
  MINOR versions; breaking changes require a MAJOR bump and a migration note.

## Development Workflow

1. Features follow Spec Kit: `/speckit-specify` → (`/speckit-clarify`) → `/speckit-plan` →
   `/speckit-tasks` → (`/speckit-analyze`) → `/speckit-implement`.
2. Each feature lives in `specs/NNN-short-name/` on a branch of the same name.
3. Plans MUST pass the Constitution Check; any violation is recorded in Complexity Tracking.
4. Merge to `main` requires green tests, an updated README for user-facing changes, and a
   preview image for visual changes.

## Governance

This constitution supersedes other practices in this repository. Amendments are made via PR
updating this file, with a version bump (MAJOR: principle removed/redefined; MINOR: principle or
section added; PATCH: wording) and a sync of dependent templates. Specs and plans are reviewed
against it; complexity must be justified.

**Version**: 1.0.0 | **Ratified**: 2026-10-17 | **Last Amended**: 2026-10-17
