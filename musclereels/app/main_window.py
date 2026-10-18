"""Editor main window: exercises | 9:16 preview | inspector, with transport and export."""
from __future__ import annotations

import copy
import math
from dataclasses import replace
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QToolTip,
                               QProgressDialog, QPushButton, QSlider, QSplitter, QStyle, QToolBar, QVBoxLayout,
                               QWidget)

from .. import __version__
from ..exercises import ExerciseDB
from ..layout import SAFE_LEFT, SAFE_RECT, SAFE_TOP, snap_to_safe_zone
from ..bodymap import DETAILED, SHAPES, GROUP_SHAPES, hit_test
from ..muscles import registry
from ..overlay import figure_frame, materialize_card, place_tiles, segment_muscles
from ..project import Project, ProjectError, Segment, load_project, make_segment, save_project
from ..video import VideoError, VideoSource
from .canvas import Canvas
from .exercise_panel import ExercisePanel
from .export_dialog import ExportDialog
from .inspector import Inspector, fmt_time
from .player import Player

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
PROJECT_EXT = {".yaml", ".yml"}
MERGE_OPACITY = 1                  # consecutive opacity-slider moves become one undo step


class _Snapshot(QUndoCommand):
    """Undo step holding the whole project before and after an edit (projects are small)."""

    def __init__(self, win: "MainWindow", text: str, before: Project, after: Project, merge_id: int = -1):
        super().__init__(text)
        self.win, self.before, self.after, self._merge_id = win, before, after, merge_id
        self._applied = True       # the edit has already been made when the command is pushed

    def id(self) -> int:
        return self._merge_id

    def mergeWith(self, other: QUndoCommand) -> bool:
        if other.id() != self._merge_id or self._merge_id == -1:
            return False
        self.after = other.after
        return True

    def redo(self) -> None:
        if self._applied:
            self._applied = False
            return
        self.win._restore(self.after)

    def undo(self) -> None:
        self.win._restore(self.before)


class MainWindow(QMainWindow):
    def __init__(self, confirm_discard: Optional[Callable[[], bool]] = None):
        super().__init__()
        self.project: Optional[Project] = None
        self.is_dirty = False
        self.selected = 0
        self.last_error = ""
        self.duration = 0.0
        self.fps = 30.0
        self.db = ExerciseDB()
        self._confirm_discard = confirm_discard or self._ask_save_changes
        self._export_dialog: Optional[ExportDialog] = None
        self.settings = QSettings("musclereels", "musclereels")
        self.undo_stack = QUndoStack(self)
        self._drag_before: Optional[Project] = None

        self.player = Player(self)
        self.canvas = Canvas()
        self.exercise_panel = ExercisePanel(self.db)
        self.inspector = Inspector()
        self._build_transport()
        self._build_toolbar()

        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.addWidget(self.canvas, 1)
        cl.addWidget(self.transport)
        split = QSplitter()
        split.addWidget(self.exercise_panel)
        split.addWidget(center)
        split.addWidget(self.inspector)
        split.setStretchFactor(1, 1)
        split.setSizes([240, 520, 280])
        self.setCentralWidget(split)
        self.setAcceptDrops(True)
        self.resize(1180, 820)

        self.player.frameReady.connect(self._on_frame)
        self.player.positionChanged.connect(self._on_position)
        self.player.playingChanged.connect(self._on_playing)
        self.player.failed.connect(lambda msg: self.show_error(f"Preview error: {msg}"))
        self.canvas.stepRequested.connect(self.step)
        self.canvas.jumpRequested.connect(lambda s: self.seek(self.position + s))
        self.canvas.playPauseRequested.connect(self.toggle_play)
        self.exercise_panel.exercise_chosen.connect(self.choose_exercise)
        self.exercise_panel.custom_requested.connect(self.add_custom)
        self.inspector.title_edited.connect(self.set_title)
        self.inspector.subtitle_edited.connect(self.set_subtitle)
        self.inspector.overlay_changed.connect(self.set_overlay_option)
        hs = self.canvas.handle_signals
        hs.started.connect(self._drag_started)
        hs.changing.connect(lambda n, dx, dy, dw: self._drag_apply(n, dx, dy, dw, final=False))
        hs.finished.connect(lambda n, dx, dy, dw: self._drag_apply(n, dx, dy, dw, final=True))
        hs.clicked.connect(lambda n, pos: self.click_muscle(n, pos))
        hs.hovered.connect(self._hover_muscle)
        self._update_ui()

    # -- construction ------------------------------------------------------------
    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(text, slot, shortcut=None):
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(shortcut)
            tb.addAction(a)
            return a

        self.act_open = act("Open…", self._open_dialog, QKeySequence.Open)
        self.act_save = act("Save", self.save, QKeySequence.Save)
        self.act_save_as = act("Save As…", self._save_as_dialog, QKeySequence.SaveAs)
        tb.addSeparator()
        self.act_export = act("Export reel…", self._export_dialog_open, QKeySequence("Ctrl+E"))
        tb.addSeparator()
        self.act_undo = self.undo_stack.createUndoAction(self, "Undo")
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_redo = self.undo_stack.createRedoAction(self, "Redo")
        self.act_redo.setShortcut(QKeySequence.Redo)
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()
        tb.addWidget(QLabel(" Detail "))
        self.detail_combo = QComboBox()
        self.detail_combo.addItem("Simple (18 groups)", "simple")
        self.detail_combo.addItem("Detailed (40 muscles)", "detailed")
        self.detail_combo.setToolTip("Detailed shows individual muscles, e.g. upper chest or side delt")
        self.detail_combo.currentIndexChanged.connect(
            lambda i: self.set_detail_level(self.detail_combo.itemData(i)))
        tb.addWidget(self.detail_combo)
        tb.addSeparator()
        self.act_safe = act("Safe zones", self.canvas.set_safe_zones_visible)
        self.act_safe.setCheckable(True)

    def _build_transport(self) -> None:
        self.transport = QWidget()
        lay = QHBoxLayout(self.transport)
        lay.setContentsMargins(8, 4, 8, 4)
        self.play_btn = QPushButton()
        self.play_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_btn.clicked.connect(self.toggle_play)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(lambda v: self.seek(v / 1000))
        self.time_label = QLabel("0:00.00 / 0:00.00")
        lay.addWidget(self.play_btn)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.time_label)

    # -- helpers -----------------------------------------------------------------
    @property
    def position(self) -> float:
        return self.player.position

    def show_error(self, msg: str) -> None:
        self.last_error = msg
        box = QMessageBox(QMessageBox.Warning, "musclereels", msg, QMessageBox.Ok, self)
        box.setAttribute(Qt.WA_DeleteOnClose)
        box.open()                                  # non-blocking

    def current_segment(self) -> Optional[Segment]:
        if not self.project or not self.project.segments:
            return None
        return self.project.segments[min(self.selected, len(self.project.segments) - 1)]

    def _mark_dirty(self) -> None:
        self.is_dirty = True
        self.player.update_project(self.project)
        self._update_ui()

    def _edit(self, text: str, fn: Callable[[], None], merge_id: int = -1) -> None:
        """Run an edit on self.project and record it as one undo step."""
        before = copy.deepcopy(self.project)
        fn()
        if self.project == before:          # nothing changed: no undo step
            return
        self.undo_stack.push(_Snapshot(self, text, before, copy.deepcopy(self.project), merge_id))
        self._mark_dirty()

    def _restore(self, snapshot: Project) -> None:
        path = self.project.path if self.project else None
        self.project = copy.deepcopy(snapshot)
        self.project.path = path
        self.selected = min(self.selected, max(0, len(self.project.segments) - 1))
        self._mark_dirty()

    def _update_ui(self) -> None:
        has = self.project is not None
        name = Path(self.project.path).name if has and self.project.path else (
            Path(self.project.input).name if has else "")
        self.setWindowTitle(f"musclereels {__version__}" + (f" — {name}{' *' if self.is_dirty else ''}" if has else ""))
        for a in (self.act_save, self.act_save_as):
            a.setEnabled(has)
        self.act_export.setEnabled(bool(has and self.project.segments))
        self.exercise_panel.setEnabled(has)
        self.transport.setEnabled(has)
        self.inspector.set_overlay(self.project.layout if has else None, self.project.theme if has else None)
        self.detail_combo.setEnabled(has)
        if has:
            self.detail_combo.blockSignals(True)
            self.detail_combo.setCurrentIndex(self.detail_combo.findData(self.project.detail_level))
            self.detail_combo.blockSignals(False)
        seg = self.current_segment()
        name = ""
        if seg is not None and seg.exercise:
            try:
                name = self.db.get(seg.exercise).name
            except KeyError:
                name = seg.exercise
        muscles = segment_muscles(seg, self.project.detail_level) if seg is not None else None
        self.inspector.set_segment(seg, name, muscles)

    # -- open --------------------------------------------------------------------
    def _open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open clip or project", self.settings.value("last_dir", ""),
                                              "Clips and projects (*.mp4 *.mov *.m4v *.avi *.mkv *.webm *.yaml *.yml)")
        if path:
            self.open_path(path)

    def open_path(self, path) -> bool:
        path = Path(path)
        if self.is_dirty and not self._confirm_discard():
            return False
        try:
            if path.suffix.lower() in PROJECT_EXT:
                project = load_project(path)
            else:
                project = Project(input=path, segments=[])
            src = VideoSource(project.input)
            if src.info.needs_proxy:
                self._prepare_with_progress(src)
        except (ProjectError, VideoError, OSError) as e:
            self.show_error(str(e))
            return False
        self.settings.setValue("last_dir", str(path.parent))
        self.project = project
        self.db = ExerciseDB(project.exercises_file)
        self.exercise_panel.set_db(self.db)
        self.selected = 0
        self.is_dirty = False
        self.undo_stack.clear()
        self.canvas.set_boxes({})
        self.duration, self.fps = src.info.duration, src.info.fps
        src.close()
        self.slider.setRange(0, int(self.duration * 1000))
        self.player.set_project(self.project, self.duration, self.fps)
        self.player.seek(0)
        self._update_ui()
        self.canvas.setFocus()
        return True

    def _prepare_with_progress(self, src: VideoSource) -> None:
        dlg = QProgressDialog("Converting variable-frame-rate clip (once)…", None, 0, 1000, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(300)

        def cb(f: float) -> None:
            dlg.setValue(int(f * 1000))
            QApplication.processEvents()

        try:
            src.prepare(cb)
        finally:
            dlg.close()

    # -- editing -----------------------------------------------------------------
    def _replace_segment(self, spec: dict, text: str = "Change exercise") -> None:
        seg = make_segment(spec, self.db)

        def fn():
            if self.project.segments:
                self.project.segments[self.selected] = seg
            else:
                self.project.segments.append(seg)
                self.selected = 0
        self._edit(text, fn)

    def _whole_clip_spec(self) -> dict:
        return {"start": 0, "end": round(self.duration, 3)}

    def choose_exercise(self, key: str) -> None:
        if not self.project:
            return
        seg = self.current_segment()
        spec = {"start": seg.start, "end": seg.end, "subtitle": seg.subtitle} if seg else self._whole_clip_spec()
        spec["exercise"] = key           # a new exercise resets title, muscles and overrides
        try:
            self._replace_segment(spec)
        except (KeyError, ValueError) as e:
            self.show_error(str(e.args[0] if e.args else e))

    def add_custom(self) -> None:
        if not self.project:
            return
        seg = self.current_segment()
        spec = {"start": seg.start, "end": seg.end, "subtitle": seg.subtitle} if seg else self._whole_clip_spec()
        spec.update({"title": "Custom Exercise", "primary": []})
        self._replace_segment(spec)

    def _edit_current(self, **changes) -> None:
        seg = self.current_segment()
        if seg is None:
            return
        spec = seg.to_dict()
        for k, v in changes.items():
            if v:
                spec[k] = v
            else:
                spec.pop(k, None)
        if spec.get("title") == (self.db.get(seg.exercise).name if seg.exercise else None):
            spec.pop("title")            # same as the exercise name: keep it linked
        try:
            new = make_segment(spec, self.db)
        except (KeyError, ValueError) as e:
            self.show_error(str(e.args[0] if e.args else e))
            self.inspector.set_segment(seg)
            return
        if new != seg:
            self._edit("Edit text", lambda: self.project.segments.__setitem__(self.selected, new))

    def set_title(self, text: str) -> None:
        self._edit_current(title=text)

    def set_subtitle(self, text: str) -> None:
        self._edit_current(subtitle=text)

    # -- overlay look ------------------------------------------------------------
    def set_overlay_option(self, key: str, value) -> None:
        """Inspector toggles: show_<element>, labels, background style, panel opacity (%)."""
        if not self.project:
            return
        seg = self.current_segment()

        def free_layout():
            lay = self.project.layout
            if lay.mode == "card" and seg is not None:
                lay = materialize_card(self.project, seg, lay, "per_element")
            return lay

        def fn():
            lay = self.project.layout
            if key == "style":
                lay = free_layout()
                figures, tiles = value in ("figures", "both"), value in ("tiles", "both")
                changes = dict(front=replace(lay.front, visible=figures), back=replace(lay.back, visible=figures))
                if tiles:
                    changes["legend"] = replace(lay.legend, visible=False)   # names are inside the boxes
                lay = replace(lay, **changes)
                tp = lay.tiles
                if tiles and not tp.visible and seg is not None:   # first time: find free space for the boxes
                    tp = place_tiles(self.project, seg, lay)
                self.project.layout = replace(lay, tiles=replace(tp, visible=tiles))
            elif key == "show_legend":
                figures = lay.front.visible or lay.back.visible
                self.project.layout = replace(lay, tile_names=bool(value),
                                              legend=replace(lay.legend, visible=bool(value) and figures))
            elif key.startswith("show_"):
                name = key[len("show_"):]
                self.project.layout = replace(lay, **{name: replace(lay.placement(name), visible=bool(value))})
            elif key == "labels":
                self.project.layout = replace(lay, labels=bool(value))
            elif key == "background":
                if lay.mode == "card":
                    if value != "grouped" and seg is not None:
                        self.project.layout = materialize_card(self.project, seg, lay, value)
                else:
                    self.project.layout = replace(lay, card=value)
            elif key == "opacity":
                theme = copy.deepcopy(self.project.theme)
                theme.card = (*theme.card[:3], round(int(value) / 100 * 255))
                self.project.theme = theme

        text = {"opacity": "Change background opacity", "background": "Change background",
                "style": "Change style"}.get(key, "Show/hide")
        self._edit(text, fn, MERGE_OPACITY if key == "opacity" else -1)

    # -- detail level and muscle picking ---------------------------------------------
    def set_detail_level(self, level: str) -> None:
        if not self.project or self.project.detail_level == level:
            return
        self._edit("Change detail", lambda: setattr(self.project, "detail_level", level))

    def _to_design(self, view: str, pos: QPointF):
        seg = self.current_segment()
        frame = figure_frame(self.project, seg, view) if (self.project and seg) else None
        if frame is None:
            return None
        fx, fy, k = frame
        return (pos.x() - fx) / k, (pos.y() - fy) / k

    def muscle_at(self, view: str, pos: QPointF):
        if view not in ("front", "back") or not self.project:
            return None
        d = self._to_design(view, pos)
        return hit_test(view, d[0], d[1], self.project.detail_level) if d else None

    def muscle_scene_pos(self, view: str, muscle: str):
        """Canvas position of a muscle's centre on a figure (used by tests and tooling)."""
        seg = self.current_segment()
        frame = figure_frame(self.project, seg, view) if seg else None
        if frame is None:
            return None
        if self.project.detail_level == "detailed":
            polys = DETAILED[view].get(muscle)
        else:
            polys = [p for v, sid in GROUP_SHAPES.get(muscle, []) if v == view for p in SHAPES[view][sid]]
        if not polys:
            return None
        poly = polys[0]
        cx = sum(x for x, _ in poly) / len(poly)
        cy = sum(y for _, y in poly) / len(poly)
        fx, fy, k = frame
        return QPointF(fx + cx * k, fy + cy * k)

    def muscle_tooltip_at(self, view: str, pos: QPointF) -> str:
        m = self.muscle_at(view, pos)
        if not m:
            return ""
        mus = registry().get(m)
        return mus.full_name if mus.full_name != mus.short_name else mus.short_name

    def _hover_muscle(self, view: str, pos: QPointF) -> None:
        text = self.muscle_tooltip_at(view, pos)
        if text:
            QToolTip.showText(QCursor.pos(), text + "\nClick: main → assisting → off")
        else:
            QToolTip.hideText()

    def click_muscle(self, view: str, pos: QPointF) -> None:
        """Cycle the clicked muscle: off → main (primary) → assisting (secondary) → off."""
        m = self.muscle_at(view, pos)
        seg = self.current_segment()
        if not m or seg is None:
            return
        prim, sec = segment_muscles(seg, self.project.detail_level)
        state = "secondary" if m in prim else ("off" if m in sec else "primary")
        if self.project.detail_level == "simple":
            members = registry().expand(m)
            lit = set(segment_muscles(seg, "detailed")[0]) | set(segment_muscles(seg, "detailed")[1])
            if not lit & set(members):
                state = "primary"

        def fn():
            s = self.project.segments[self.selected]
            s.overrides = {**s.overrides, m: state}
        self._edit(f"Set {registry().display_name(m)} {state}", fn)

    # -- moving / resizing elements on the canvas ----------------------------------
    def _on_frame(self, t: float, image, boxes: dict) -> None:
        self.canvas.set_frame(image)
        self.canvas.set_boxes(boxes)

    def _drag_started(self, name: str) -> None:
        seg = self.current_segment()
        if not self.project or seg is None:
            return
        self.pause()
        self._drag_before = copy.deepcopy(self.project)
        if self.project.layout.mode == "card":     # the card becomes separate, movable items
            self.project.layout = materialize_card(self.project, seg, self.project.layout, "per_element")
        self._drag_base = self.project.layout

    def _drag_apply(self, name: str, dx: float, dy: float, dw: float, final: bool) -> None:
        if self._drag_before is None:
            return
        base = self._drag_base.placement(name)
        p = replace(base, x=round(base.x + dx), y=round(base.y + dy), width=max(40, round(base.width + dw)))
        if final:
            x0, y0, x1, y1 = self.canvas.handles[name].scene_box()
            size = (p.width if name == "title" else x1 - x0, y1 - y0)
            p = snap_to_safe_zone(p, size)
        self.project.layout = replace(self._drag_base, **{name: p})
        if not final:
            self.player.update_project(self.project)
            return
        before, self._drag_before = self._drag_before, None
        what = "Resize" if dw else "Move"
        self.undo_stack.push(_Snapshot(self, f"{what} {name}", before, copy.deepcopy(self.project)))
        self._mark_dirty()

    # -- transport ---------------------------------------------------------------
    def seek(self, t: float) -> None:
        self.player.seek(t)

    def step(self, frames: int) -> None:
        self.player.step(frames)

    def play(self) -> None:
        self.player.play()

    def pause(self) -> None:
        self.player.pause()

    def toggle_play(self) -> None:
        self.player.toggle()

    def _on_position(self, t: float) -> None:
        if not self.slider.isSliderDown():
            self.slider.setValue(int(t * 1000))
        self.time_label.setText(f"{fmt_time(t)} / {fmt_time(self.duration)}")

    def _on_playing(self, playing: bool) -> None:
        icon = QStyle.SP_MediaPause if playing else QStyle.SP_MediaPlay
        self.play_btn.setIcon(self.style().standardIcon(icon))

    # -- save --------------------------------------------------------------------
    def save(self) -> bool:
        if not self.project:
            return False
        if self.project.path is None:
            return self._save_as_dialog()
        return self.save_as(self.project.path)

    def _save_as_dialog(self) -> bool:
        if not self.project:
            return False
        default = self.project.path or Path(self.project.input).with_suffix(".yaml")
        path, _ = QFileDialog.getSaveFileName(self, "Save project", str(default), "Project (*.yaml)")
        return self.save_as(path) if path else False

    def save_as(self, path) -> bool:
        try:
            self.project.validate()
            save_project(self.project, path)
        except (ProjectError, OSError) as e:
            self.show_error(str(e))
            return False
        self.is_dirty = False
        self._update_ui()
        return True

    # -- export ------------------------------------------------------------------
    def _export_dialog_open(self) -> None:
        if not self.project:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export reel", str(self.project.output), "MP4 video (*.mp4)")
        if path:
            self.export_to(path)

    def export_to(self, path) -> Optional[ExportDialog]:
        if not self.project or not self.project.segments:
            self.show_error("Pick an exercise before exporting.")
            return None
        try:
            self.project.validate()
        except ProjectError as e:
            self.show_error(str(e))
            return None
        self.pause()
        dlg = ExportDialog(self.project, Path(path), self)
        self._export_dialog = dlg
        dlg.open()
        dlg.start()
        return dlg

    # -- window events -----------------------------------------------------------
    def _ask_save_changes(self) -> bool:
        r = QMessageBox.question(self, "Unsaved changes", "Save changes to this project?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            return self.save()
        return r == QMessageBox.Discard

    def closeEvent(self, event) -> None:
        if self.is_dirty and not self._confirm_discard():
            event.ignore()
            return
        self.player.stop()
        event.accept()

    def dragEnterEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls and Path(urls[0].toLocalFile()).suffix.lower() in VIDEO_EXT | PROJECT_EXT:
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        if urls:
            self.open_path(urls[0].toLocalFile())
