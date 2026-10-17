"""Editor main window: exercises | 9:16 preview | inspector, with transport and export."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QProgressDialog, QPushButton, QSlider, QSplitter, QStyle, QToolBar, QVBoxLayout,
                               QWidget)

from .. import __version__
from ..exercises import ExerciseDB
from ..project import Project, ProjectError, Segment, load_project, make_segment, save_project
from ..video import VideoError, VideoSource
from .canvas import Canvas
from .exercise_panel import ExercisePanel
from .export_dialog import ExportDialog
from .inspector import Inspector, fmt_time
from .player import Player

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
PROJECT_EXT = {".yaml", ".yml"}


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

        self.player.frameReady.connect(lambda t, img: self.canvas.set_frame(img))
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
        seg = self.current_segment()
        name = ""
        if seg is not None and seg.exercise:
            try:
                name = self.db.get(seg.exercise).name
            except KeyError:
                name = seg.exercise
        self.inspector.set_segment(seg, name)

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
    def _replace_segment(self, spec: dict) -> None:
        seg = make_segment(spec, self.db)
        if self.project.segments:
            self.project.segments[self.selected] = seg
        else:
            self.project.segments.append(seg)
            self.selected = 0
        self._mark_dirty()

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
            self.project.segments[self.selected] = new
            self._mark_dirty()

    def set_title(self, text: str) -> None:
        self._edit_current(title=text)

    def set_subtitle(self, text: str) -> None:
        self._edit_current(subtitle=text)

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
