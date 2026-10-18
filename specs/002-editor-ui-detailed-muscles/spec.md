# Feature Specification: Reel Editor App with Detailed Muscle Map

**Feature Branch**: `002-editor-ui-detailed-muscles`

**Created**: 2026-10-17

**Status**: Draft

**Input**: User description: "Extend the tool into a UI app where we can flexibly add the front / back dummy human with muscles, and show more specific muscles."

> Builds on the baseline in [`001-reel-rendering`](../001-reel-rendering/spec.md). Everything 001 guarantees
> (reel-ready output, safe zones, local-only processing, CLI and YAML scripts) still holds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Build a reel visually (Priority: P1)

A creator opens the editor app, loads a gym clip, picks an exercise, and sees the reel straight
away in a 9:16 preview with the title and body figures on top. They play/scrub the clip, then
export an Instagram-ready reel without touching the terminal or a YAML file.

**Why this priority**: The app only earns its place if it replaces the command line for the
everyday job. On its own this is a usable MVP.

**Independent Test**: A user who has never used the CLI loads a clip, chooses "Squat", exports,
and uploads the file to Instagram without further editing.

**Acceptance Scenarios**:

1. **Given** the app is open, **When** the user drops a video file onto the window (or uses Open), **Then** the clip appears in a 9:16 preview, reframed exactly as the exported reel will be.
2. **Given** a loaded clip, **When** the user searches for and selects an exercise (aliases and close matches work), **Then** the title and both figures appear with the correct muscles highlighted.
3. **Given** a loaded clip, **When** the user plays or scrubs, **Then** the preview shows the overlay as it will look at that moment, including fades and pulsing.
4. **Given** a ready project, **When** the user exports, **Then** they see progress, can cancel, and get a file with the same guarantees as a CLI render (001 FR-001, FR-009).
5. **Given** an unsupported or unreadable file, **When** it is loaded, **Then** the app explains the problem and stays usable.

---

### User Story 2 - Place the front and back figures freely (Priority: P1)

The creator wants the figures where they look best for each clip, not in a fixed card. They can
drag, resize and show or hide the front figure and the back figure independently. Moving a
figure while the athlete is in frame keeps the figures from covering the movement.

**Why this priority**: This is the headline request ("flexibly add the front / back dummy").

**Independent Test**: Show only the back figure, put it large in the bottom-left above the
caption area, export, and confirm the export matches the preview.

**Acceptance Scenarios**:

1. **Given** a project, **When** the user drags a figure, **Then** it moves freely; **When** they drag a corner handle, **Then** it resizes with its proportions locked.
2. **Given** both figures, **When** the user hides one, **Then** only the other is shown and exported.
3. **Given** the user places a figure partly inside Instagram's reserved areas, **When** they release it, **Then** the reserved areas are shown and the figure snaps back inside the safe zone (with a way to override deliberately).
4. **Given** the user has a layout they like, **When** they save it as a named layout preset, **Then** they can apply it to other projects in one click.
5. **Given** figure placement, **When** the user toggles the title, card background, legend chips and "FRONT/BACK" labels, or lowers the panel opacity, **Then** each changes independently, so a reel can show only the figures on a see-through panel.
6. **Given** several segments (Story 3), **When** the user changes a figure's position for one segment only, **Then** other segments keep the project's default placement.

---

### User Story 2b - Muscle boxes style (Priority: P1)

Instead of (or next to) the full-body figures, the creator shows **one box per worked muscle**: a
zoomed close-up of the body around that muscle, lit red for main muscles and orange for assisting
ones, with the muscle's name underneath.

**Why this priority**: Requested by the creator; makes each muscle readable on a phone screen.

**Independent Test**: Pick "Deadlift", choose Style → Muscle boxes, export; the reel shows 7 boxes
(3 red, 4 orange), each framing its muscle, and no full-body figures.

**Acceptance Scenarios**:

1. **Given** an exercise, **When** the user picks Style → Muscle boxes, **Then** each worked muscle gets its own square close-up box, main muscles first, and the full-body figures are hidden; Style → Both shows figures and boxes; Full body returns to figures only.
2. **Given** muscle boxes, **When** the user drags or resizes them, **Then** they move as one group and resizing changes the box size (up to 4 per row), kept inside the safe zone.
3. **Given** muscle boxes, **When** "Muscle names" is off, **Then** the boxes show no text.
4. **Given** a paired muscle (e.g. quads), **Then** its box frames one side of the body with enough surroundings to recognise where it is.

---

### User Story 3 - Several exercises on a timeline (Priority: P2)

For a full-session clip the creator marks where each exercise starts and ends on a timeline under
the preview, and gives each segment its own exercise and subtitle.

**Why this priority**: Covers the multi-exercise format from 001 Story 2 without hand-written YAML.

**Independent Test**: Make three segments on one clip by dragging on the timeline, export, and confirm each overlay appears only in its range.

**Acceptance Scenarios**:

1. **Given** a clip, **When** the user adds a segment at the playhead and drags its edges, **Then** start/end update live; segments cannot overlap.
2. **Given** segments exist, **When** the user selects one, **Then** they can edit its exercise, title, subtitle, and muscle selection.
3. **Given** a timeline, **When** the user sets trim in/out points, **Then** only that range is exported, audio in sync.
4. **Given** a project made in the app, **When** saved, **Then** it is stored as an edit script the CLI can render to an identical result, and edit scripts written by hand open in the app.

---

### User Story 4 - Show specific muscles (Priority: P1)

The creator wants to teach precisely: an incline press hits the *upper* chest, a hammer curl
works the *brachialis and brachioradialis*, Bulgarian split squats hit the *glute medius*. The
figures can be shown at a **detailed** level with individual muscles and heads, as well as at the
current simple level.

**Why this priority**: The second explicit request, and the main thing that sets these reels apart from generic "chest day" graphics.

**Independent Test**: Set "Incline Bench Press" to detailed level and check that the upper chest is primary while mid/lower chest are not highlighted, and the legend reads "Upper Chest".

**Acceptance Scenarios**:

1. **Given** any exercise, **When** the user switches the project between Simple and Detailed, **Then** the figures redraw at that level and the legend uses the matching names.
2. **Given** Detailed level, **When** an exercise defines specific muscles (e.g. upper chest), **Then** only those are highlighted; **When** it only defines a broad group (e.g. chest), **Then** every muscle in that group is highlighted.
3. **Given** a figure, **When** the user clicks a muscle on it, **Then** it cycles primary → secondary → off for the current segment, and the legend updates.
4. **Given** the user hovers a muscle, **Then** its name is shown, so they can learn the map without a reference.
5. **Given** existing edit scripts and custom exercise files using simple muscle names, **When** opened, **Then** they still work and render the same at Simple level.

---

### User Story 5 - Zoom in on a muscle (Priority: P2)

To make a point ("look at the side delt") the creator adds a **detail inset**: an enlarged
close-up of one body region (e.g. shoulder, arm, thigh), drawn in the same style and also
movable/resizable on the canvas.

**Why this priority**: Strong for educational reels, but only after the detailed map exists.

**Independent Test**: Add a "Shoulder" inset for Lateral Raise, place it top-right, and confirm the side delt is clearly visible and labelled in the export.

**Acceptance Scenarios**:

1. **Given** a segment, **When** the user adds an inset and chooses a region (or "auto: around the primary muscles"), **Then** an enlarged view of that region appears with its muscles highlighted.
2. **Given** an inset, **When** the user chooses "label muscles", **Then** the highlighted muscles in the inset carry name callouts.
3. **Given** an inset, **When** the user moves/resizes or hides it, **Then** it behaves like the figures (safe-zone snapping, per-segment override).
4. **Given** an inset, **When** the user picks a zoom-in entrance, **Then** it animates in from the matching spot on the full figure.

### Edge Cases

- Very short segment (< 1 s): fades shorten so the overlay is still fully visible for at least a moment.
- Figure scaled so small that muscles are unreadable: the app warns below a minimum size; legend names still carry the information.
- Detailed level with many highlighted muscles: legend groups by broad area ("Chest: Upper, Mid") so it fits.
- Exercise defines both a group and one of its sub-muscles: the more specific level wins for that muscle.
- Clip with variable frame rate or rotation metadata (phone footage): preview and export show the same orientation and timing.
- Very long clip (10+ min): the preview stays responsive; export memory stays bounded.
- App closed with unsaved changes: the user is asked to save; an autosave lets them recover after a crash.
- Custom exercise file contains an unknown muscle: the app shows which file and line, and the valid names.

## Requirements *(mandatory)*

### Functional Requirements

**Editor app**

- **FR-001**: Users MUST be able to open a video by drag-and-drop or file picker and see it in a live 9:16 preview that matches the export frame for frame.
- **FR-002**: Users MUST be able to play, pause, scrub, and step frame by frame.
- **FR-003**: Users MUST be able to choose an exercise from a searchable list (names, aliases, close matches) or define a custom one by clicking muscles.
- **FR-004**: Users MUST be able to edit title and subtitle text and see changes immediately.
- **FR-005**: Users MUST be able to export with progress and cancel, producing output identical to a CLI render of the same project.
- **FR-006**: Projects MUST save to and open from the same edit-script format the CLI uses, extended for the new options and still readable by the CLI. Scripts from 001 MUST open unchanged.
- **FR-007**: The app MUST autosave and offer recovery after an unexpected exit.
- **FR-008**: Users MUST be able to undo/redo every edit.

**Flexible figures**

- **FR-009**: The front figure and back figure MUST each be independently movable, resizable (proportions locked), and showable/hideable.
- **FR-010**: Users MUST be able to toggle the card background, the legend, and view labels independently, and choose where the legend sits.
- **FR-010a**: Users MUST be able to turn every text element off (title, muscle names, FRONT/BACK labels) so a reel can show the figures only, and set the panel background opacity from 0 % (fully see-through) to 100 %.
- **FR-010b**: Users MUST be able to choose a **Muscle boxes** style: one square zoomed close-up per worked muscle (main muscles first, coloured by role, optional name), shown instead of or together with the full-body figures, movable and resizable as one element, and available to the CLI as the `muscle-boxes` layout preset.
- **FR-011**: The canvas MUST show Instagram's reserved areas while editing and keep overlay elements inside the safe zone by default, with an explicit override.
- **FR-012**: Placement MUST have a project default with optional per-segment overrides.
- **FR-013**: Users MUST be able to save, name, apply, and delete layout presets; presets MUST be reusable across projects.
- **FR-014**: The current fixed card layouts (left/right/center) MUST be available as built-in presets.

**Timeline**

- **FR-015**: Users MUST be able to create, select, move, resize, and delete non-overlapping segments on a timeline, and set trim in/out.
- **FR-016**: Each segment MUST hold its own exercise, title, subtitle, muscle selection, and optional placement overrides.

**Detailed muscle map**

- **FR-017**: The body map MUST support two detail levels, Simple (the 18 groups from 001) and Detailed, selectable per project.
- **FR-018**: The Detailed level MUST include at least these muscles, each drawn as its own region and named in the legend:
  - **Neck**: sternocleidomastoid
  - **Chest**: upper, mid, lower pectoralis; serratus anterior
  - **Shoulders**: anterior, lateral, posterior deltoid
  - **Upper back**: upper, middle, lower trapezius; rhomboids; teres major; infraspinatus (rotator cuff)
  - **Lats**: latissimus dorsi
  - **Lower back**: erector spinae
  - **Arms**: biceps long head, biceps short head, brachialis; triceps long, lateral, medial head
  - **Forearms**: brachioradialis, wrist flexors, wrist extensors
  - **Core**: upper rectus abdominis, lower rectus abdominis, external obliques
  - **Hips**: gluteus maximus, gluteus medius, hip flexors, adductors
  - **Thighs**: rectus femoris, vastus lateralis, vastus medialis; biceps femoris, semitendinosus/semimembranosus
  - **Lower legs**: gastrocnemius, soleus, tibialis anterior
- **FR-019**: Every detailed muscle MUST belong to exactly one Simple group, so that naming a group highlights all its muscles and Simple level shows a group as lit if any of its muscles is.
- **FR-020**: Exercise definitions MUST accept both group names and specific muscle names; the built-in database MUST be updated to specific muscles where there is clear exercise-science consensus (e.g. incline press → upper chest; hammer curl → brachialis, brachioradialis; lateral raise → lateral deltoid; Bulgarian split squat → glute medius secondary).
- **FR-021**: Users MUST be able to click a muscle on a figure to cycle primary → secondary → off, and hover to see its name.
- **FR-022**: Muscle names MUST have a short display name for the legend and a full anatomical name for hover/inset labels.

**Detail inset**

- **FR-023**: Users MUST be able to add zero or more detail insets per segment, each showing an enlarged region: shoulder, chest, arm, forearm, core, back, hip/glute, thigh, lower leg; or *auto* (framed around the segment's primary muscles).
- **FR-024**: Insets MUST support muscle name callouts, the same placement controls as figures (FR-009, FR-011, FR-012), and an optional zoom-in entrance animation.

**Compatibility and principles**

- **FR-025**: The CLI MUST gain access to every new option (detail level, figure placement, insets) through edit scripts; the app MUST NOT have render features the CLI lacks (Constitution IV).
- **FR-026**: The app MUST work fully offline with no account, and no clip or project data leaving the machine (Constitution I).
- **FR-027**: The app MUST run on Windows 10+ and macOS 12+.

### Key Entities

- **Project**: source clip, trim range, detail level, default layout, segments, theme. Saved as an edit script.
- **Segment**: time range, exercise, title, subtitle, muscle selection, optional layout overrides, insets.
- **Muscle**: id, short name, full anatomical name, view(s) where it appears, parent Simple group.
- **Muscle Group (Simple)**: one of the 18 groups from 001; contains one or more muscles.
- **Exercise**: name, aliases, primary and secondary muscles (groups and/or specific muscles).
- **Layout**: per element (front figure, back figure, legend, title, card): visibility, position, size. Layout presets are named, reusable layouts.
- **Detail Inset**: region (or auto), position, size, labels on/off, entrance animation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A first-time user goes from opening the app to an exported single-exercise reel in under 3 minutes with no instructions.
- **SC-002**: Repositioning a figure and seeing the result takes under 2 seconds (live preview, no render wait).
- **SC-003**: Preview plays smoothly (no visible stutter) for 1080p clips on a typical laptop.
- **SC-004**: An exported reel is visually identical to its preview and to a CLI render of the same saved project.
- **SC-005**: 100% of 001 edit scripts and custom exercise files open and render with the same result at Simple level.
- **SC-006**: In an informal test with 5+ gym-goers, viewers name the specific highlighted muscle (e.g. "upper chest", "side delt") correctly in at least 4 out of 5 cases.
- **SC-007**: A three-segment session reel can be built on the timeline in under 5 minutes.

## Assumptions

- **Single clip per project.** Cutting/joining several clips, music, transitions and text animations beyond the title are out of scope. Creators use their usual editor for those, or a later feature.
- **Art style.** The detailed map keeps the current flat, stylised vector look (clear on a phone screen) rather than realistic anatomical illustration.
- **Platforms.** Windows and macOS desktops. iOS/Android and a phone app are out of scope (see the platform discussion from setup). Linux works on a best-effort basis.
- **Views.** Front and back only; side views and figure rotation are out of scope.
- **Body type.** One neutral body shape; male/female or physique variants are out of scope for this feature.
- **Anatomy** is simplified for a general fitness audience; deep or small muscles (e.g. pec minor, supraspinatus, piriformis) are left out unless they are commonly taught in gym content. Mappings follow Constitution III (under-claim when unsure).
- **Pose tracking**, exercise auto-detection and rep counting stay out of scope (README roadmap).
- Users can install a desktop app; it should not require Python or a terminal for everyday use.
