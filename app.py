import os
import sys
import time
import threading
from pathlib import Path

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
    bundled = resource_path(os.path.join("ffmpeg", "ffmpeg.exe"))
    if os.path.exists(bundled):
        return bundled
    return shutil.which("ffmpeg") if "shutil" in globals() else None


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
        try:
            ff = resource_path(os.path.join("ffmpeg", "ffmpeg.exe"))
            if not os.path.exists(ff):
                import shutil
                ff = shutil.which("ffmpeg")
            if not ff:
                raise RuntimeError("FFmpeg was not found.")

            ydl_opts = {
                "outtmpl": os.path.join(self.folder, "%(title)s.%(ext)s"),
                "noplaylist": True,
                "progress_hooks": [self._hook],
                "ffmpeg_location": os.path.dirname(ff),
                "quiet": True,
                "no_warnings": True,
                "retries": 5,
                "fragment_retries": 5,
            }

            if self.mode == "MP3":
                ydl_opts.update({
                    "format": "bestaudio/best",
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "0",
                    }],
                })
            else:
                formats = {
                    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
                    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
                    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
                    "2160p": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
                    "Best": "bestvideo+bestaudio/best",
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
                ydl_opts["download_ranges"] = download_range_func(
                    None, [(start_sec, end_sec)]
                )
                ydl_opts["force_keyframes_at_cuts"] = True

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.info.emit(info)
                title = info.get("title") or "YouTube download"
                ydl.download([self.url])

            if self.cancel_requested:
                self.failed.emit("Download cancelled.")
            else:
                self.finished_ok.emit(title)

        except Exception as exc:
            message = str(exc)
            if "SMF_CANCELLED" in message:
                self.failed.emit("Download cancelled.")
            else:
                self.failed.emit(message)


class PillButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)


class ModeCard(QPushButton):
    def __init__(self, title, subtitle, icon_text, parent=None):
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.icon_text = icon_text
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(82)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        selected = self.isChecked()
        bg = QColor("#2a172a" if selected else PANEL2)
        border = QColor(PINK if selected else BORDER)
        painter.setBrush(bg)
        painter.setPen(border)
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 12, 12)

        painter.setPen(QColor(PINK if self.icon_text == "▶" else "#a34cff"))
        painter.setFont(QFont("Segoe UI Symbol", 20, QFont.Bold))
        painter.drawText(22, 39, self.icon_text)

        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        painter.drawText(70, 31, self.title)

        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(70, 56, self.subtitle)

        painter.setPen(QColor(TEXT))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rect.right() - 32, rect.center().y() - 9, 18, 18)
        if selected:
            painter.setBrush(QColor(TEXT))
            painter.drawEllipse(rect.right() - 27, rect.center().y() - 4, 8, 8)


class QualityButton(QPushButton):
    def __init__(self, text, sub, parent=None):
        super().__init__(parent)
        self.text_main = text
        self.sub = sub
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(68)
        self.setMinimumWidth(115)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        selected = self.isChecked()
        painter.setBrush(QColor("#2a172a" if selected else PANEL2))
        painter.setPen(QColor(PINK if selected else BORDER))
        painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 11, 11)
        painter.setPen(QColor(TEXT))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(r.center().x() - 40, 29, self.text_main)
        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(r.center().x() - 40, 49, self.sub)


class SMFWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setWindowTitle(APP_NAME)
        self.resize(1180, 820)
        self.setMinimumSize(1000, 740)
        self.setStyleSheet(self.styles())
        self.build_ui()
        self.reset_state()

    def styles(self):
        return f"""
        QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI'; }}
        QLineEdit {{ background: {FIELD}; border: 1px solid {BORDER}; border-radius: 9px;
                     padding: 12px 14px; color: {TEXT}; font-size: 14px; }}
        QLineEdit:focus {{ border: 1px solid #536178; }}
        QPushButton {{ border: 0; }}
        QProgressBar {{ background: #1b222d; border: 0; border-radius: 5px; height: 8px; }}
        QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                          stop:0 {PINK}, stop:1 {PURPLE}); border-radius: 5px; }}
        """

    def label(self, text, size=10, color=TEXT, bold=False):
        w = QLabel(text)
        w.setStyleSheet(f"color:{color}; font-size:{size}px; font-weight:{'600' if bold else '400'};")
        return w

    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 20, 28, 22)
        outer.setSpacing(12)

        header = QHBoxLayout()
        logo = QLabel("▶")
        logo.setAlignment(Qt.AlignCenter)
        logo.setFixedSize(52, 52)
        logo.setStyleSheet(f"background:{PINK}; color:white; border-radius:14px; font-size:25px; font-weight:700;")
        header.addWidget(logo)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(self.label("SMF YT Downloader  ", 20, TEXT, True))
        title_box.addWidget(self.label("FAST  •  HIGH QUALITY  •  SIMPLE", 9, MUTED, True))
        header.addLayout(title_box)
        header.addStretch()

        version = self.label("v1.0", 9, "#e9d2ff", True)
        version.setStyleSheet("background:#31105d; color:#e9d2ff; padding:4px 9px; border-radius:9px;")
        header.addWidget(version)
        header.addSpacing(18)
        header.addWidget(self.label("SMF Studio", 16, TEXT))
        outer.addLayout(header)

        card = QFrame()
        card.setStyleSheet(f"QFrame {{background:{PANEL}; border:1px solid {BORDER}; border-radius:15px;}}")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 20)
        card_layout.setSpacing(16)

        # URL
        url_title = self.label("🔗   YouTube Video URL", 13, TEXT, True)
        card_layout.addWidget(url_title)
        url_row = QHBoxLayout()
        url_row.setSpacing(10)
        self.url = QLineEdit()
        self.url.setPlaceholderText("Paste YouTube video URL here…")
        url_row.addWidget(self.url, 1)
        paste = QPushButton("📋  Paste")
        paste.setMinimumWidth(110)
        paste.setMinimumHeight(44)
        paste.setStyleSheet(self.secondary_button())
        paste.clicked.connect(lambda: self.url.setText(QApplication.clipboard().text()))
        url_row.addWidget(paste)
        card_layout.addLayout(url_row)

        # Format cards
        card_layout.addWidget(self.label("▦   Format", 13, TEXT, True))
        format_row = QHBoxLayout()
        format_row.setSpacing(12)
        self.video_mode = ModeCard("Video", "Download video with sound", "▶")
        self.audio_mode = ModeCard("Audio", "Download audio only", "♫")
        self.video_mode.clicked.connect(lambda: self.select_mode("Video"))
        self.audio_mode.clicked.connect(lambda: self.select_mode("MP3"))
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.video_mode)
        self.mode_group.addButton(self.audio_mode)
        format_row.addWidget(self.video_mode, 1)
        format_row.addWidget(self.audio_mode, 1)
        card_layout.addLayout(format_row)

        # Quality
        card_layout.addWidget(self.label("⚙   Video Quality", 13, TEXT, True))
        qrow = QHBoxLayout()
        qrow.setSpacing(10)
        self.quality_group = QButtonGroup(self)
        self.quality_group.setExclusive(True)
        self.quality_buttons = []
        qualities = [("720p", "HD"), ("1080p", "FULL HD"), ("1440p", "2K QHD"),
                     ("2160p", "4K UHD"), ("Best", "AVAILABLE")]
        for main, sub in qualities:
            b = QualityButton(main, sub)
            b.clicked.connect(lambda checked=False, x=main: self.select_quality(x))
            self.quality_group.addButton(b)
            self.quality_buttons.append(b)
            qrow.addWidget(b)
        card_layout.addLayout(qrow)

        # Video length
        card_layout.addWidget(self.label("◷   Video Length", 13, TEXT, True))
        length_row = QHBoxLayout()
        length_row.setSpacing(16)

        radio_box = QVBoxLayout()
        self.full_radio = QRadioButton("Full Video  (Download complete video)")
        self.custom_radio = QRadioButton("Custom Length  (Download specific part)")
        self.full_radio.setStyleSheet(self.radio_style(False))
        self.custom_radio.setStyleSheet(self.radio_style(True))
        self.full_radio.toggled.connect(self.toggle_custom)
        self.full_radio.setChecked(True)
        radio_box.addWidget(self.full_radio)
        radio_box.addWidget(self.custom_radio)
        length_row.addLayout(radio_box, 1)

        time_box = QFrame()
        time_box.setStyleSheet(f"QFrame{{background:{PANEL2}; border:1px solid {BORDER}; border-radius:12px;}}")
        tgrid = QGridLayout(time_box)
        tgrid.setContentsMargins(16, 12, 16, 12)
        tgrid.addWidget(self.label("Start Time", 10, MUTED), 0, 0)
        tgrid.addWidget(self.label("End Time", 10, MUTED), 0, 2)
        self.start_edit = QLineEdit("00:00:00")
        self.end_edit = QLineEdit("00:01:00")
        self.start_edit.setEnabled(False)
        self.end_edit.setEnabled(False)
        tgrid.addWidget(self.start_edit, 1, 0)
        tgrid.addWidget(self.end_edit, 1, 2)
        tgrid.addWidget(self.label("Format: HH:MM:SS   (Example: 00:05:30)", 9, MUTED), 2, 0, 1, 3)
        length_row.addWidget(time_box, 1)
        card_layout.addLayout(length_row)

        # Save
        card_layout.addWidget(self.label("▱   Save To", 13, TEXT, True))
        save_row = QHBoxLayout()
        self.folder = QLineEdit(str(Path.home() / "Downloads" / "SMF YT Downloads"))
        save_row.addWidget(self.folder, 1)
        browse = QPushButton("📁  Browse")
        browse.setMinimumWidth(120)
        browse.setMinimumHeight(44)
        browse.setStyleSheet(self.secondary_button())
        browse.clicked.connect(self.choose_folder)
        save_row.addWidget(browse)
        card_layout.addLayout(save_row)

        # Action row
        action = QHBoxLayout()
        action.setSpacing(10)
        self.download_btn = QPushButton("⬇   DOWNLOAD")
        self.download_btn.setMinimumHeight(54)
        self.download_btn.setStyleSheet(self.download_style())
        self.download_btn.clicked.connect(self.start_download)

        self.cancel_btn = QPushButton("■   CANCEL")
        self.cancel_btn.setMinimumHeight(54)
        self.cancel_btn.setMinimumWidth(140)
        self.cancel_btn.setStyleSheet(self.cancel_style())
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.cancel_btn.setEnabled(False)

        action.addWidget(self.download_btn, 1)
        action.addWidget(self.cancel_btn)
        card_layout.addLayout(action)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        card_layout.addWidget(self.progress)

        self.status = self.label("Ready. Paste a YouTube URL to begin.", 9, MUTED)
        card_layout.addWidget(self.status)

        outer.addWidget(card, 1)

        # Bottom active-download card
        bottom = QFrame()
        bottom.setStyleSheet(f"QFrame {{background:{PANEL}; border:1px solid {BORDER}; border-radius:14px;}}")
        bl = QGridLayout(bottom)
        bl.setContentsMargins(18, 14, 18, 14)
        bl.setColumnStretch(1, 1)

        thumb = QLabel("4K")
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setFixedSize(152, 88)
        thumb.setStyleSheet("background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #37435c, stop:1 #111927); color:white; border-radius:9px; font-size:25px; font-weight:700;")
        bl.addWidget(thumb, 0, 0, 3, 1)

        self.file_title = self.label("No active download", 12, TEXT, True)
        self.file_meta = self.label("—", 9, MUTED)
        self.progress_label = self.label("Waiting", 9, MUTED)
        self.speed_label = self.label("-- MB/s", 9, MUTED)
        self.eta_label = self.label("--:--:--", 9, MUTED)

        bl.addWidget(self.file_title, 0, 1, 1, 3)
        bl.addWidget(self.file_meta, 1, 1, 1, 3)
        bl.addWidget(self.progress_label, 2, 1)
        self.bottom_progress = QProgressBar()
        self.bottom_progress.setRange(0, 100)
        self.bottom_progress.setValue(0)
        self.bottom_progress.setTextVisible(False)
        bl.addWidget(self.bottom_progress, 3, 1, 1, 2)
        bl.addWidget(self.speed_label, 3, 3, Qt.AlignRight)
        bl.addWidget(self.eta_label, 4, 3, Qt.AlignRight)
        outer.addWidget(bottom)

    def radio_style(self, accent):
        return f"""
        QRadioButton {{
            color:{TEXT}; spacing:10px; font-size:13px;
        }}
        QRadioButton::indicator {{
            width:16px; height:16px; border-radius:8px;
            border:2px solid {'#777f8d' if not accent else '#747d8a'};
            background:transparent;
        }}
        QRadioButton::indicator:checked {{
            border:2px solid {PINK}; background:{PINK};
        }}
        """

    def secondary_button(self):
        return f"""
        QPushButton {{
            background:{PANEL2}; color:{TEXT}; border:1px solid {BORDER};
            border-radius:9px; padding:10px 14px; font-size:12px; font-weight:600;
        }}
        QPushButton:hover {{ border-color:#536178; }}
        """

    def download_style(self):
        return f"""
        QPushButton {{
            color:white; border-radius:10px; padding:12px; font-size:15px; font-weight:700;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {PINK}, stop:1 {PURPLE});
        }}
        QPushButton:hover {{ background:#ff4777; }}
        QPushButton:disabled {{ background:#424953; color:#aeb5bf; }}
        """

    def cancel_style(self):
        return f"""
        QPushButton {{
            background:{PANEL2}; color:{TEXT}; border:1px solid {BORDER};
            border-radius:10px; padding:12px 18px; font-size:13px; font-weight:700;
        }}
        QPushButton:hover {{ border-color:#536178; }}
        """

    def reset_state(self):
        self.select_mode("Video")
        self.select_quality("1080p")
        self.bottom_progress.setValue(0)
        self.file_title.setText("No active download")
        self.file_meta.setText("Choose a format and quality to start.")
        self.progress_label.setText("Waiting")
        self.speed_label.setText("-- MB/s")
        self.eta_label.setText("--:--:--")

    def select_mode(self, mode):
        if mode == "Video":
            self.video_mode.setChecked(True)
        else:
            self.audio_mode.setChecked(True)
        enabled = mode == "Video"
        for b in self.quality_buttons:
            b.setEnabled(enabled)
        self.quality_buttons[1].setChecked(True)

    def select_quality(self, quality):
        mapping = {"720p": 0, "1080p": 1, "1440p": 2, "2160p": 3, "Best": 4}
        idx = mapping[quality]
        self.quality_buttons[idx].setChecked(True)

    def toggle_custom(self, checked):
        self.start_edit.setEnabled(checked)
        self.end_edit.setEnabled(checked)

    def choose_folder(self):
        selected = QFileDialog.getExistingDirectory(self, "Choose save folder", self.folder.text())
        if selected:
            self.folder.setText(selected)

    def start_download(self):
        url = self.url.text().strip()
        if not url:
            self.status.setText("Paste a YouTube URL first.")
            self.status.setStyleSheet(f"color:{ERROR if 'ERROR' in globals() else '#ff8e8e'}; font-size:9px;")
            return

        folder = self.folder.text().strip()
        os.makedirs(folder, exist_ok=True)

        mode = "MP3" if self.audio_mode.isChecked() else "Video"
        quality = ["720p", "1080p", "1440p", "2160p", "Best"][
            next(i for i, b in enumerate(self.quality_buttons) if b.isChecked())
        ]

        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.show()
        self.progress.setValue(0)
        self.bottom_progress.setValue(0)
        self.status.setText("Analyzing video and starting download...")
        self.file_title.setText("Preparing download…")

        self.worker = DownloadWorker(
            url=url, mode=mode, quality=quality,
            custom=self.custom_radio.isChecked(),
            start_time=self.start_edit.text(),
            end_time=self.end_edit.text(),
            folder=folder
        )
        self.worker.info.connect(self.on_info)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_success)
        self.worker.failed.connect(self.on_failure)
        self.worker.start()

    def cancel_download(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.status.setText("Cancelling download…")

    def on_info(self, info):
        title = info.get("title") or "YouTube download"
        duration = info.get("duration") or 0
        h, rem = divmod(int(duration), 3600)
        m, s = divmod(rem, 60)
        duration_text = f"{h:02d}:{m:02d}:{s:02d}"
        mode = "MP3" if self.audio_mode.isChecked() else "MP4"
        quality = info.get("height") or "Best"
        self.file_title.setText(title)
        self.file_meta.setText(f"{quality}p  •  {mode}  •  {duration_text}")
        self.progress_label.setText("Downloading…")

    def on_progress(self, pct, speed, eta, state):
        value = max(0, min(100, int(pct)))
        self.progress.setValue(value)
        self.bottom_progress.setValue(value)
        self.progress_label.setText(f"Downloading…  {value}%")
        self.speed_label.setText(speed)
        self.eta_label.setText(eta)

    def on_success(self, title):
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(100)
        self.bottom_progress.setValue(100)
        self.status.setStyleSheet(f"color:{GREEN}; font-size:9px;")
        self.status.setText("Download complete.")
        self.progress_label.setText("Completed  •  100%")

    def on_failure(self, error):
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status.setStyleSheet(f"color:#ff8e8e; font-size:9px;")
        self.status.setText(error[:160])
        self.progress_label.setText("Stopped")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = SMFWindow()
    window.show()
    sys.exit(app.exec())
