# Data Model: Reel Editor App with Detailed Muscle Map

Coordinates: **canvas** = 1080×1920 px (export frame), **design** = 200×440 per figure (body art).
Times are seconds (float). All entities are plain Python dataclasses in the core; the app holds them and edits them only through undoable commands.

## Muscle

| Field | Type | Rules |
|---|---|---|
| `id` | str | snake_case, unique, e.g. `upper_chest` |
| `short_name` | str | legend label, ≤ 16 chars, e.g. "Upper Chest" |
| `full_name` | str | hover/inset label, e.g. "Pectoralis major (clavicular head)" |
| `group` | GroupId | exactly one of the 18 Simple groups (FR-019) |
| `views` | set[`front`\|`back`] | at least one; must have polygons in each listed view |

### Detailed muscles (40) and parent groups

| Group (Simple) | Detailed muscles (`id`) | Views |
|---|---|---|
| chest | `upper_chest`, `mid_chest`, `lower_chest` | front |
| front_delts | `anterior_delt` | front |
| side_delts | `lateral_delt` | front, back |
| rear_delts | `posterior_delt` | back |
| traps | `upper_traps` (front + back), `mid_traps`, `lower_traps` (back), `sternocleidomastoid` (front) | front, back |
| rhomboids | `rhomboids`, `infraspinatus` | back |
| lats | `latissimus_dorsi` (back, plus its visible edge on the front), `teres_major` (back) | front, back |
| lower_back | `erector_spinae` | back |
| biceps | `biceps_long_head`, `biceps_short_head`, `brachialis` | front |
| triceps | `triceps_long_head`, `triceps_lateral_head`, `triceps_medial_head` | back |
| forearms | `brachioradialis`, `wrist_flexors` (front), `wrist_extensors` (back) | front, back |
| abs | `upper_abs`, `lower_abs` | front |
| obliques | `external_obliques`, `serratus_anterior` | front |
| glutes | `gluteus_maximus`, `gluteus_medius` | back |
| quads | `rectus_femoris`, `vastus_lateralis`, `vastus_medialis`, `hip_flexors` | front |
| hamstrings | `biceps_femoris`, `medial_hamstrings` | back |
| adductors | `adductors` | front |
| calves | `gastrocnemius`, `soleus`, `tibialis_anterior` | back, front |

Parent choices for neck, serratus, hip flexors and tibialis: see [research.md R6](research.md#r6-parent-groups-for-muscles-outside-the-18-simple-groups).

## MuscleRef (used everywhere muscles are named)

A string that is a muscle `id`, a Simple group id, or an alias (`shoulders`, `core`, `pecs`, …).
Resolution: alias → groups/muscles; group → all its muscles. Unknown → error with the file/line and valid names.

## Exercise

| Field | Type | Rules |
|---|---|---|
| `key` | str | normalised snake_case, unique (custom files override built-ins) |
| `name`, `aliases` | str, list[str] | aliases unique across DB |
| `primary`, `secondary` | list[MuscleRef] | `primary` non-empty |

Resolved at **Detailed** level: expand refs to muscles; a muscle in both lists is primary; if an exercise lists a group and one of its muscles in different lists, the specific muscle's list wins for that muscle.
Resolved at **Simple** level: a group is primary if any of its muscles is primary, else secondary if any is secondary.

## Activation (resolved muscle state for a segment)

`dict[muscle_id, "primary" | "secondary"]`, computed from the exercise and then the segment's `overrides`
(muscle-click edits from FR-021: `{muscle_id: primary|secondary|off}`).

## ElementPlacement

| Field | Type | Rules |
|---|---|---|
| `visible` | bool | |
| `x`, `y` | int | top-left in canvas px |
| `width` | int | ≥ element minimum (figures: 120 px warns below); height derived from aspect |
| `allow_outside_safe_zone` | bool | default false → box clamped into safe rect on edit and on load |

## Layout

| Field | Type |
|---|---|
| `title`, `front`, `back`, `legend` | ElementPlacement |
| `card` | `grouped` \| `per_element` \| `none` |
| `labels` | bool (FRONT/BACK view labels) |

**LayoutPreset** = `name` + Layout. Built-ins: `card-left`, `card-right`, `card-center` (equal to 001's positions), `split-corners` (front bottom-left, back top-right), `back-only-large`.

`SegmentLayoutOverride` = partial Layout: only the fields given replace the project default (FR-012).

## DetailInset

| Field | Type | Rules |
|---|---|---|
| `region` | `auto` \| `shoulder` \| `chest` \| `arm` \| `forearm` \| `core` \| `back` \| `hip` \| `thigh` \| `lower_leg` | `auto` frames the segment's primary muscles |
| `view` | `front` \| `back` \| `auto` | `auto` picks the view showing most primary area |
| `placement` | ElementPlacement | same rules as figures |
| `labels` | bool | name callouts for lit muscles in the inset |
| `entrance` | `fade` \| `zoom` | `zoom` animates from the region on the full figure |

Each region maps to a crop box in design space (`data/bodymap/regions.json`). `auto` = bounding box of primary muscle polygons, padded 15 %, aspect clamped to 3:4 … 4:3.

## Segment

| Field | Type | Rules |
|---|---|---|
| `start`, `end` | float | `0 ≤ start < end`; no overlap with other segments |
| `exercise` | str? | key or alias; optional if `primary` given |
| `title`, `subtitle` | str, str? | title required (from exercise if not set) |
| `primary`, `secondary` | list[MuscleRef]? | replace the exercise's lists if present |
| `overrides` | dict[muscle_id, primary\|secondary\|off] | from muscle clicks |
| `layout` | SegmentLayoutOverride? | |
| `insets` | list[DetailInset] | default empty |

## Project (edit script v2)

| Field | Type | Rules |
|---|---|---|
| `version` | 2 | missing ⇒ v1, migrated on load |
| `input`, `output` | path | relative to the project file |
| `trim` | `{in, out}` \| bool | bool kept for v1 compatibility |
| `detail_level` | `simple` \| `detailed` | default `simple` (keeps v1 output identical) |
| `layout` | Layout \| preset name | v1 `position: left` ⇒ preset `card-left` |
| `segments` | list[Segment] | sorted by start |
| `theme`, `exercises_file`, `pulse_hz`, `crf`, `preset`, `audio` | as in 001 | |

### State transitions (app)

```
Empty ──open clip──▶ Editing (clean) ──edit──▶ Editing (dirty) ──save──▶ Editing (clean)
                          │                        │  └─30 s──▶ autosave written
                          └──────export──────▶ Exporting ──done/cancel──▶ previous state
Launch with newer autosave ──▶ Recovery prompt ──accept──▶ Editing (dirty) / ──discard──▶ Empty
```
