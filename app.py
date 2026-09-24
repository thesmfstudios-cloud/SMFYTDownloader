import os
import sys
import time
import threading
import shutil
import tempfile
import re
from pathlib import Path

import imageio_ffmpeg

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap, QColor
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QFrame,
    QHBoxLayout, QVBoxLayout, QGridLayout, QButtonGroup, QRadioButton,
    QProgressBar, QFileDialog, QMessageBox, QSizePolicy
)

import yt_dlp
from yt_dlp.utils import download_range_func


APP_NAME = "SMF YT Downloader"

BG = "#0b0e14"
PANEL = "#10151e"
PANEL2 = "#151b25"
FIELD = "#121923"
BORDER = "#2b3442"
TEXT = "#f4f6f8"
MUTED = "#9da6b4"
PINK = "#ff2e68"
PURPLE = "#9b2cff"
GREEN = "#75e4a2"


def resource_path(name: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def ffmpeg_path() -> str | None:
    # Prefer the FFmpeg binary shipped inside imageio-ffmpeg/PyInstaller.
    # Do not blindly traverse PATH: some Windows environments contain
    # virtual/untrusted mount entries that can raise WinError 448.
    candidates = []

    try:
        package_dir = Path(imageio_ffmpeg.__file__).resolve().parent
        candidates.extend(package_dir.glob("binaries/ffmpeg*.exe"))
    except Exception:
        pass

    try:
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled:
            candidates.append(Path(bundled))
    except Exception:
        pass

    for candidate in candidates:
        try:
            candidate = candidate.resolve()
            if candidate.is_file() and "cua-driver" not in str(candidate).lower():
                return str(candidate)
        except OSError:
            continue

    # Final fallback only when PATH lookup is safe.
    try:
        fallback = shutil.which("ffmpeg")
        if fallback and "cua-driver" not in fallback.lower():
            return fallback
    except OSError:
        pass

    return None


def seconds_from_hms(value: str) -> float:
    value = value.strip()
    parts = value.split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Time must be HH:MM:SS, MM:SS or SS")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        raise ValueError("Invalid time value")
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    return nums[0]


class DownloadWorker(QThread):
    progress = Signal(float, str, str, str)
    info = Signal(dict)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, url: str, mode: str, quality: str, custom: bool,
                 start_time: str, end_time: str, folder: str):
        super().__init__()
        self.url = url
        self.mode = mode
        self.quality = quality
        self.custom = custom
        self.start_time = start_time
        self.end_time = end_time
        self.folder = folder
        self.cancel_requested = False

    def cancel(self):
        self.cancel_requested = True

    def _hook(self, data):
        if self.cancel_requested:
            raise yt_dlp.utils.DownloadError("SMF_CANCELLED")

        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes") or 0
            pct = (done / total * 100) if total else 0
            speed = self._fmt_speed(data.get("speed"))
            eta = self._fmt_eta(data.get("eta"))
            self.progress.emit(pct, speed, eta, data.get("status", "downloading"))

    @staticmethod
    def _fmt_speed(value):
        if not value:
            return "--"
        units = ["B/s", "KB/s", "MB/s", "GB/s"]
        n = float(value)
        i = 0
        while n >= 1024 and i < len(units) - 1:
            n /= 1024
            i += 1
        return f"{n:.1f} {units[i]}"

    @staticmethod
    def _fmt_eta(value):
        if value is None:
            return "--"
        m, s = divmod(int(value), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def run(self):
        temp_dir = Path(tempfile.mkdtemp(prefix="smfyt_"))
        try:
            ff = ffmpeg_path()
            if not ff:
                raise RuntimeError("FFmpeg was not found. The bundled FFmpeg runtime could not be located.")

            ydl_opts = {
                "outtmpl": str(temp_dir / "%(title)s.%(ext)s"),
                "noplaylist": True,
                "progress_hooks": [self._hook],
                "ffmpeg_location": ff,
                "quiet": True,
                "no_warnings": True,
                "retries": 5,
                "fragment_retries": 5,
                "windowsfilenames": True,
            }

            source_is_h264 = False

            if self.mode == "MP3":
                ydl_opts.update({
                    "format": "bestaudio[acodec^=mp4a]/bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "0",
                    }],
                })
            else:
                formats = {
                    "720p": "bestvideo[vcodec^=avc1][height<=720]+bestaudio[acodec^=mp4a]/best[ext=mp4][vcodec^=avc1][height<=720]/bestvideo[height<=720]+bestaudio/best[height<=720]",
                    "1080p": "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[acodec^=mp4a]/best[ext=mp4][vcodec^=avc1][height<=1080]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                    "1440p": "bestvideo[vcodec^=avc1][height<=1440]+bestaudio[acodec^=mp4a]/best[ext=mp4][vcodec^=avc1][height<=1440]/bestvideo[height<=1440]+bestaudio/best[height<=1440]",
                    "2160p": "bestvideo[vcodec^=avc1][height<=2160]+bestaudio[acodec^=mp4a]/best[ext=mp4][vcodec^=avc1][height<=2160]/bestvideo[height<=2160]+bestaudio/best[height<=2160]",
                    "Best": "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/best[ext=mp4][vcodec^=avc1]/bestvideo+bestaudio/best",
                }
                ydl_opts.update({
                    "format": formats[self.quality],
                    "merge_output_format": "mp4",
                })

            if self.custom:
                start_sec = seconds_from_hms(self.start_time or "00:00:00")
                end_sec = seconds_from_hms(self.end_time)
                if end_sec <= start_sec:
                    raise ValueError("End time must be greater than start time.")
                ydl_opts["download_ranges"] = download_range_func(None, [(start_sec, end_sec)])
                ydl_opts["force_keyframes_at_cuts"] = True

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.info.emit(info)

                if self.mode != "MP3":
                    requested = info.get("requested_formats") or []
                    codecs = [f.get("vcodec", "") for f in requested if f.get("vcodec") and f.get("vcodec") != "none"]
                    if not codecs:
                        codecs = [info.get("vcodec") or ""]
                    source_is_h264 = any(c.startswith("avc1") for c in codecs)

                if self.cancel_requested:
                    raise yt_dlp.utils.DownloadError("SMF_CANCELLED")

                title = info.get("title") or "YouTube download"
                ydl.download([self.url])

            if self.cancel_requested:
                raise yt_dlp.utils.DownloadError("SMF_CANCELLED")

            media_files = [
                p for p in temp_dir.iterdir()
                if p.is_file() and p.suffix.lower() in {".mp4", ".m4v", ".webm", ".mkv", ".mov", ".mp3", ".m4a"}
            ]
            if not media_files:
                raise RuntimeError("Downloaded media file was not found.")

            source = max(media_files, key=lambda p: p.stat().st_size)
            safe_title = re.sub(r'[<>:"/\\|?*]', "_", title).strip(" .") or "SMF_YT_Downloader"

            if self.mode == "MP3":
                final_path = Path(self.folder) / f"{safe_title}.mp3"
                if source.suffix.lower() == ".mp3":
                    shutil.move(str(source), str(final_path))
                else:
                    self._run_ffmpeg(
                        ff,
                        ["-y", "-i", str(source), "-vn", "-c:a", "libmp3lame", "-q:a", "0", str(final_path)],
                        duration=info.get("duration") or 0,
                    )
            else:
                final_path = Path(self.folder) / f"{safe_title}.mp4"
                if source_is_h264:
                    args = [
                        "-y", "-i", str(source),
                        "-map", "0:v:0", "-map", "0:a:0?",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(final_path)
                    ]
                    self._run_ffmpeg(ff, args, duration=info.get("duration") or 0)
                else:
                    args = [
                        "-y", "-i", str(source),
                        "-map", "0:v:0", "-map", "0:a:0?",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(final_path)
                    ]
                    self._run_ffmpeg(ff, args, duration=info.get("duration") or 0)

            if self.cancel_requested:
                raise yt_dlp.utils.DownloadError("SMF_CANCELLED")

            if final_path.exists() and final_path.stat().st_size > 0:
                self.finished_ok.emit(title)
            else:
                raise RuntimeError("Final output file was not created.")

        except Exception as exc:
            message = str(exc)
            if "SMF_CANCELLED" in message:
                self.failed.emit("Download cancelled.")
            else:
                self.failed.emit(message)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            self.current_process = None

    def _run_ffmpeg(self, ff: str, args: list[str], duration: float = 0):
        if self.cancel_requested:
            raise yt_dlp.utils.DownloadError("SMF_CANCELLED")

        command = [ff, "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats"] + args
        self.current_process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace"
        )
        try:
            for line in self.current_process.stdout:
                if self.cancel_requested:
                    try:
                        self.current_process.terminate()
                    except OSError:
                        pass
                    raise yt_dlp.utils.DownloadError("SMF_CANCELLED")
                line = line.strip()
                if duration and line.startswith("out_time_us="):
                    try:
                        done_sec = int(line.split("=", 1)[1]) / 1_000_000
                        pct = max(0.0, min(100.0, done_sec / duration * 100.0))
                        self.progress.emit(pct, "Converting", "--", "converting")
                    except ValueError:
                        pass

            code = self.current_process.wait()
            if code != 0:
                raise RuntimeError("FFmpeg conversion failed. The video could not be converted to a Premiere-ready MP4.")
        finally:
            self.current_process = None

