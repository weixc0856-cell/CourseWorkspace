"""PrintWindow-based recorder for GPU-rendered windows such as VS Code."""

from __future__ import annotations

import ctypes
import subprocess
import threading
import time
from pathlib import Path

from .session_runner import _window_rect


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32),
        ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32),
        ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16),
        ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32),
        ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32),
        ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


class PrintWindowRecorder:
    def __init__(
        self,
        hwnd: int,
        output: Path,
        fps: int,
        log_path: Path | None = None,
    ):
        rect = _window_rect(hwnd)
        if rect is None:
            raise RuntimeError("cannot read window rectangle")
        self.hwnd = hwnd
        self.width = rect[2]
        self.height = rect[3]
        self.fps = fps
        self.output = output
        self.log_path = log_path
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen | None = None
        self._log = None
        self._capture_error = None

    def _open_ffmpeg(self):
        log = (
            self.log_path.open("wb")
            if self.log_path is not None
            else subprocess.DEVNULL
        )
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgra",
            "-s",
            f"{self.width}x{self.height}",
            "-r",
            str(self.fps),
            "-i",
            "-",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            str(self.output),
        ]
        self._log = log
        return subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=log,
        )

    def _capture(self):
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc_window = user32.GetWindowDC(self.hwnd)
        if not hdc_window:
            raise RuntimeError("GetWindowDC failed")
        hdc_mem = gdi32.CreateCompatibleDC(hdc_window)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_window, self.width, self.height)
        try:
            gdi32.SelectObject(hdc_mem, hbmp)
            if not user32.PrintWindow(self.hwnd, hdc_mem, 2):
                raise RuntimeError("PrintWindow failed")
            info = _BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            info.bmiHeader.biWidth = self.width
            info.bmiHeader.biHeight = -self.height
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            info.bmiHeader.biCompression = 0
            buffer = ctypes.create_string_buffer(self.width * self.height * 4)
            copied = gdi32.GetDIBits(
                hdc_mem,
                hbmp,
                0,
                self.height,
                buffer,
                ctypes.byref(info),
                0,
            )
            if copied != self.height:
                raise RuntimeError(f"GetDIBits copied {copied} rows")
            return buffer.raw
        finally:
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(self.hwnd, hdc_window)

    def _loop(self):
        frame_interval = 1.0 / self.fps
        next_frame = time.monotonic()
        while not self._stop.is_set():
            try:
                frame = self._capture()
            except Exception as exc:  # noqa: BLE001
                self._capture_error = str(exc)
                break
            try:
                self._process.stdin.write(frame)
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as exc:
                self._capture_error = str(exc)
                break
            next_frame += frame_interval
            delay = next_frame - time.monotonic()
            if delay > 0:
                time.sleep(delay)

    def start(self) -> "PrintWindowRecorder":
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self._process = self._open_ffmpeg()
        time.sleep(0.3)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
        if self._process is not None:
            try:
                if self._process.stdin is not None:
                    self._process.stdin.close()
            except OSError:
                pass
            try:
                self._process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self._process.terminate()
                self._process.wait(timeout=10)
        if self._log is not None and self._log is not subprocess.DEVNULL:
            self._log.close()
