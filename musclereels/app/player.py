"""Preview playback: decoding + compositing on a worker thread, timed from the UI thread.

Frames are produced by the same `frame_for_time` the export uses (at half resolution), so the
preview shows exactly what will be rendered.
"""
from __future__ import annotations

import copy
import threading
import time
from collections import OrderedDict
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QImage

from ..project import Project
from ..render import SpriteCache, frame_for_time
from ..video import VideoSource

PREVIEW_SCALE = 0.5
SOURCE_CACHE_FRAMES = 120        # decoded source frames kept around the playhead (~110 MB at 1080p)


def to_qimage(frame: np.ndarray) -> QImage:
    h, w = frame.shape[:2]
    return QImage(frame.data, w, h, 3 * w, QImage.Format_BGR888).copy()


class FrameWorker(QObject):
    """Lives on a worker thread. Only the most recent request is rendered (older ones are dropped)."""
    frameReady = Signal(float, QImage)
    failed = Signal(str)
    _wake = Signal()

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._latest: Optional[tuple[Project, float]] = None
        self._path = None
        self._video: Optional[VideoSource] = None
        self._sprites = SpriteCache()
        self._frames: OrderedDict[int, np.ndarray] = OrderedDict()
        self._wake.connect(self._process)

    def request(self, project: Project, t: float) -> None:      # called from the UI thread
        with self._lock:
            pending = self._latest is not None
            self._latest = (project, t)
        if not pending:
            self._wake.emit()

    def _source_frame(self, t: float) -> np.ndarray:
        idx = self._video.index_at(t)
        frame = self._frames.get(idx)
        if frame is None:
            frame = self._video.read_index(idx)
            self._frames[idx] = frame
            if len(self._frames) > SOURCE_CACHE_FRAMES:
                self._frames.popitem(last=False)
        else:
            self._frames.move_to_end(idx)
        return frame

    @Slot()
    def _process(self) -> None:
        with self._lock:
            job, self._latest = self._latest, None
        if job is None:
            return
        project, t = job
        try:
            if self._path != project.input:
                if self._video:
                    self._video.close()
                self._video = VideoSource(project.input)
                self._video.prepare()                 # reuses the cached proxy for VFR clips
                self._path = project.input
                self._frames.clear()
            frame = frame_for_time(project, t, source_frame=self._source_frame(t), scale=PREVIEW_SCALE,
                                   cache=self._sprites)
            self.frameReady.emit(t, to_qimage(frame))
        except Exception as e:                        # keep the worker alive; report to the UI
            self.failed.emit(str(e))

    @Slot()
    def shutdown(self) -> None:
        if self._video:
            self._video.close()


class Player(QObject):
    """UI-side controller: position, play/pause clock, and frame requests to the worker."""
    frameReady = Signal(float, QImage)
    positionChanged = Signal(float)
    playingChanged = Signal(bool)
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = QThread()
        self._worker = FrameWorker()
        self._worker.moveToThread(self._thread)
        self._worker.frameReady.connect(self.frameReady)
        self._worker.failed.connect(self.failed)
        self._thread.start()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._project: Optional[Project] = None
        self.duration = 0.0
        self.fps = 30.0
        self.position = 0.0
        self._play_origin = (0.0, 0.0)          # (position, monotonic time) when play started

    # -- setup -----------------------------------------------------------------
    def set_project(self, project: Optional[Project], duration: float = 0.0, fps: float = 30.0) -> None:
        self._project = copy.deepcopy(project) if project else None
        if duration:
            self.duration, self.fps = duration, fps
        self.refresh()

    def update_project(self, project: Project) -> None:
        """Call after every edit: the worker gets an immutable snapshot."""
        self._project = copy.deepcopy(project)
        if not self.is_playing:
            self.refresh()

    # -- transport -------------------------------------------------------------
    @property
    def is_playing(self) -> bool:
        return self._timer.isActive()

    def snap(self, t: float) -> float:
        last = max(0.0, (round(self.duration * self.fps) - 1) / self.fps)
        return min(max(0.0, round(t * self.fps) / self.fps), last)

    def seek(self, t: float) -> None:
        self.position = self.snap(t)
        self.positionChanged.emit(self.position)
        self.refresh()
        if self.is_playing:
            self._play_origin = (self.position, time.monotonic())

    def step(self, frames: int) -> None:
        self.seek((round(self.position * self.fps) + frames) / self.fps)

    def play(self) -> None:
        if not self._project or self.is_playing:
            return
        if self.position >= self.snap(self.duration):
            self.position = 0.0
        self._play_origin = (self.position, time.monotonic())
        self._timer.start(max(5, int(1000 / self.fps)))
        self.playingChanged.emit(True)

    def pause(self) -> None:
        if self.is_playing:
            self._timer.stop()
            self.playingChanged.emit(False)

    def toggle(self) -> None:
        self.pause() if self.is_playing else self.play()

    def _tick(self) -> None:
        start_pos, start_time = self._play_origin
        t = start_pos + (time.monotonic() - start_time)
        if t >= self.duration:
            self.position = self.snap(self.duration)
            self.pause()
        else:
            self.position = self.snap(t)
        self.positionChanged.emit(self.position)
        self.refresh()

    def refresh(self) -> None:
        if self._project is not None:
            self._worker.request(self._project, self.position)

    def stop(self) -> None:
        self.pause()
        if self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
            self._worker.shutdown()
