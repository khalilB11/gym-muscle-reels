# Contract: Editor window

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Open  Save  Export   Undo Redo        Detail: [Simple|Detailed]  Preset ▾ │
├──────────────┬────────────────────────────────┬──────────────────────────┤
│ Exercises    │                                │ Inspector                │
│ [search…  ]  │      9:16 canvas preview       │  Segment: Incline Bench  │
│ Bench Press  │   (video + overlay elements,   │  Title / Subtitle        │
│ Incline …    │    drag / resize handles,      │  Muscles (click figure)  │
│ Squat        │    safe zones shaded)          │  Elements: ☑Front ☑Back  │
│ …            │                                │   ☑Legend ☑Title  Card ▾ │
│ + Custom     │                                │  Insets: + Add           │
├──────────────┴────────────────────────────────┴──────────────────────────┤
│ ▶ 0:12.4 / 0:41   |====[Incline]====|==[Lateral]==|=[Hammer]=|  ◀ trim ▶ │
└──────────────────────────────────────────────────────────────────────────┘
```

| Interaction | Result | Spec |
|---|---|---|
| Drop a video on the window / Open | Clip loaded; proxy built with progress if needed | FR-001 |
| Space / ← → / Shift+← → | Play-pause / step frame / jump 1 s | FR-002 |
| Click an exercise in the list | Applies to the selected segment, or creates one covering the clip if none exist | FR-003 |
| Drag element / drag corner | Move / resize (aspect locked); snap into safe zone on release; Alt to skip snapping | FR-009, FR-011 |
| Hover muscle | Tooltip with full name | FR-021 |
| Click muscle | primary → secondary → off for the current segment | FR-021 |
| Shift-drag on timeline / `S` | New segment / split at playhead | FR-015 |
| Right-click element → "This segment only" | Following edits become a segment override | FR-012 |
| Preset ▾ → Save current… | Saves the layout as a named preset | FR-013 |
| Ctrl/Cmd+Z, Shift+Ctrl/Cmd+Z | Undo / redo any edit | FR-008 |
| Export | Progress dialog with Cancel; "Show in folder" when done | FR-005 |
