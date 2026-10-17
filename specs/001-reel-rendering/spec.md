# Feature Specification: Muscle-Activation Reel Rendering (Baseline)

**Feature Branch**: `001-reel-rendering`

**Created**: 2026-10-17

**Status**: Implemented (baseline for v0.1.0)

**Input**: User description: "A local video editing tool for the gym that shows which muscles each exercise works, for making Instagram Reels."

> This spec records the behaviour already shipped in v0.1.0 so that later features
> (`002-…`, `003-…`) can build on an agreed baseline. Changes to anything below go through a new spec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One clip, one exercise (Priority: P1)

A creator has a clip of themselves doing one exercise. They run a single command naming the
exercise and get a vertical Reel with the exercise title and a body map highlighting the muscles
it works, ready to upload.

**Why this priority**: This is the core value — turning a raw gym clip into an educational Reel in one step.

**Independent Test**: Run `musclereels render clip.mp4 -e squat` and upload the result to Instagram without further editing.

**Acceptance Scenarios**:

1. **Given** a vertical clip and a known exercise, **When** the user renders it, **Then** the output is 1080×1920 H.264 with the original audio, the exercise title at the top, and a front/back body map where primary muscles are red and secondary muscles orange.
2. **Given** a landscape clip, **When** rendered with default settings, **Then** the whole clip is shown centred over a blurred, darkened copy of itself (no important content cropped).
3. **Given** an exercise alias (e.g. `rdl`, `ohp`), **When** rendered, **Then** it resolves to the canonical exercise.
4. **Given** a misspelt exercise, **When** rendered, **Then** the tool exits with an error listing the closest matches.

---

### User Story 2 - Several exercises in one Reel (Priority: P2)

A creator films a session in one clip and wants each exercise labelled during its time range.

**Why this priority**: Multi-exercise "workout" Reels are a common format; enables full-session content.

**Independent Test**: Render `examples/session.yaml` with 3+ segments and confirm each overlay appears only within its time range.

**Acceptance Scenarios**:

1. **Given** an edit script with non-overlapping segments, **When** rendered, **Then** each segment shows its own title and muscles, fading in and out at its boundaries.
2. **Given** overlapping segments, **When** loaded, **Then** the tool refuses with a message naming both segments.
3. **Given** `trim: true`, **When** rendered, **Then** the output contains only the span from the first segment's start to the last segment's end, with audio kept in sync.
4. **Given** a segment with `title` and `primary` but no `exercise`, **When** rendered, **Then** a custom overlay is shown.

---

### User Story 3 - Check the look before rendering (Priority: P2)

A creator wants to see the overlay design quickly without waiting for a full render.

**Why this priority**: Fast iteration on titles, positions and themes.

**Independent Test**: `musclereels preview -e deadlift -o p.png` produces a 1080×1920 PNG in under 5 seconds.

**Acceptance Scenarios**:

1. **Given** an exercise, **When** previewing, **Then** a single fully-lit still is written.
2. **Given** `--video clip.mp4 --at 0:04`, **When** previewing, **Then** that frame is used as the background.

---

### User Story 4 - Make it my own (Priority: P3)

A creator adds exercises the tool doesn't know and adjusts colours/fonts to match their brand.

**Why this priority**: Long-tail exercises and branding matter for regular posting, but defaults cover most use.

**Independent Test**: Render with `--exercises-file my.yaml` using a custom exercise and a theme with a custom primary colour.

**Acceptance Scenarios**:

1. **Given** a custom exercises YAML, **When** an exercise key matches a built-in, **Then** the custom definition wins.
2. **Given** an unknown muscle id in any YAML, **When** loaded, **Then** the tool fails with the list of valid ids and aliases.
3. **Given** a theme with hex colours and a font path, **When** rendered, **Then** the overlay uses them.

### Edge Cases

- Clip shorter than the segment end, or `end: end` → overlay runs to the end of the clip, no fade-out.
- Clip without an audio track → silent output, no error.
- Many muscles → legend chips wrap; card shrinks (down to 50 %) to stay above the caption safe zone.
- Very long titles → font shrinks to fit the safe width (minimum 36 px).
- ffmpeg missing → clear install instructions per OS; non-zero exit.
- Unreadable/missing input → clear error, non-zero exit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST output 1080×1920 H.264 (`yuv420p`, `+faststart`) with AAC audio copied from the source when present.
- **FR-002**: System MUST reframe any input aspect ratio to 9:16 via `cover` (crop) or `blur` (letterbox on blurred background); `auto` picks `cover` for aspect ≤ 0.75, else `blur`.
- **FR-003**: System MUST render a front and back body map with 18 muscle groups: chest, front/side/rear delts, traps, upper back (rhomboids), lats, lower back, biceps, triceps, forearms, abs, obliques, glutes, quads, hamstrings, adductors, calves.
- **FR-004**: System MUST colour primary muscles and secondary muscles distinctly; a muscle listed as both is shown as primary only.
- **FR-005**: System MUST ship a built-in exercise database (currently 36 exercises) with aliases, mapping each exercise to primary and secondary muscles.
- **FR-006**: System MUST accept a single exercise via CLI, or a YAML edit script of time segments (seconds or `m:ss` timestamps, `end` keyword).
- **FR-007**: System MUST reject overlapping or zero-length segments and unknown exercises/muscles with actionable errors.
- **FR-008**: The overlay MUST fade in/out (~0.35 s) and the highlighted muscles MUST pulse at a configurable rate.
- **FR-009**: All overlay elements MUST remain within the Instagram safe zone (top 250 px, bottom 450 px, left 60 px, right 180 px).
- **FR-010**: Users MUST be able to position the card (`left`, `right`, `center`) and scale it.
- **FR-011**: Users MUST be able to extend/override exercises and set theme colours and fonts via YAML.
- **FR-012**: System MUST provide `render`, `preview`, `list` (exercises / `--muscles`) and `demo` commands.
- **FR-013**: System MUST run fully offline with no data leaving the machine.

### Key Entities

- **Muscle**: an id (e.g. `quads`), display name, and the body-map regions (front/back) it lights up. Aliases expand to one or more muscles.
- **Exercise**: key, display name, aliases, ordered primary and secondary muscles.
- **Segment**: start/end time, title, optional subtitle, primary and secondary muscles (from an exercise or custom).
- **Job (edit script)**: input/output paths, segments, layout (position, fit, scale), trim, pulse rate, encode quality, theme.
- **Theme**: primary/secondary/inactive/card/text colours and optional font paths.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user goes from installed tool to an uploadable Reel with one command in under 2 minutes for a 30 s clip.
- **SC-002**: 100 % of renders upload to Instagram Reels without re-encoding warnings or cropping of the overlay by platform UI.
- **SC-003**: A 60 s 1080p clip renders in ≤ 3× its duration on a typical laptop CPU.
- **SC-004**: `musclereels preview` returns in under 5 seconds.
- **SC-005**: Viewers can identify the targeted muscle groups from the overlay alone (validated informally with 5+ viewers).

## Assumptions

- Users can install Python ≥ 3.9 and ffmpeg and are comfortable running a terminal command.
- Clips are typical phone recordings (≤ 4K, ≤ 60 fps, a few minutes long).
- Muscle mappings are simplified for a general audience, not clinical accuracy.
- Instagram Reels safe zones remain roughly as of 2026; values are constants that can be updated.
- Pose tracking, exercise auto-detection, rep counting and a GUI are out of scope for this baseline (see README roadmap).
