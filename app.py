import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

APP_NAME = "SMF YT Downloader"
BG = "#0b0d10"
PANEL = "#14171c"
PANEL_2 = "#1a1f26"
BORDER = "#2a3038"
TEXT = "#f3f5f7"
MUTED = "#8f98a5"
ACCENT = "#ffffff"
ACCENT_TEXT = "#111318"
SUCCESS = "#8ee6ad"
ERROR = "#ff8e8e"

def which(name):
    return shutil.which(name) or shutil.which(name + ".exe")

def set_status(text, kind="normal"):
    def update():
        status_var.set(text[-160:])
        if kind == "success":
            status_label.configure(fg=SUCCESS)
        elif kind == "error":
            status_label.configure(fg=ERROR)
        else:
            status_label.configure(fg=MUTED)
    root.after(0, update)

def browse_folder():
    selected = filedialog.askdirectory(initialdir=folder_var.get())
    if selected:
        folder_var.set(selected)

def select_mode(mode):
    mode_var.set(mode)
    video_btn.configure(bg=ACCENT if mode == "Video" else PANEL_2,
                         fg=ACCENT_TEXT if mode == "Video" else TEXT)
    mp3_btn.configure(bg=ACCENT if mode == "MP3" else PANEL_2,
                      fg=ACCENT_TEXT if mode == "MP3" else TEXT)
    for w in quality_buttons:
        w.configure(state="normal" if mode == "Video" else "disabled")

def select_quality(value):
    quality_var.set(value)
    for label, button in quality_buttons_map.items():
        button.configure(bg=ACCENT if label == value else PANEL_2,
                         fg=ACCENT_TEXT if label == value else TEXT)

def toggle_custom():
    state = "normal" if custom_var.get() else "disabled"
    start_entry.configure(state=state, fg=TEXT if state == "normal" else MUTED)
    end_entry.configure(state=state, fg=TEXT if state == "normal" else MUTED)
    custom_hint.configure(text="Choose any start/end time" if state == "normal" else "Full video / full audio")

def choose_name_safe(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)

def build_command(url):
    mode = mode_var.get()
    quality = quality_var.get()
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--newline"]

    if mode == "MP3":
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
    else:
        formats = {
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "1440p / 2K": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
            "2160p / 4K": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
            "Best available": "bestvideo+bestaudio/best",
        }
        cmd += ["-f", formats[quality], "--merge-output-format", "mp4"]

    if custom_var.get():
        start = start_var.get().strip() or "00:00:00"
        end = end_var.get().strip()
        if not end:
            raise ValueError("Custom length ke liye End time required hai.")
        cmd += ["--download-sections", f"*{start}-{end}", "--force-keyframes-at-cuts"]

    output_template = os.path.join(folder_var.get(), "%(title)s.%(ext)s")
    cmd += ["-o", output_template, url]
    return cmd

def start_download():
    url = url_var.get().strip()
    if not url:
        set_status("YouTube URL missing hai.", "error")
        return

    out = folder_var.get().strip()
    if not os.path.isdir(out):
        set_status("Valid save folder select karo.", "error")
        return

    if not which("ffmpeg"):
        set_status("FFmpeg missing hai. FFmpeg PATH me available hona chahiye.", "error")
        return

    try:
        cmd = build_command(url)
    except Exception as exc:
        set_status(str(exc), "error")
        return

    download_button.configure(state="disabled", bg="#606873")
    cancel_button.configure(state="normal")
    progress.configure(mode="indeterminate")
    progress.pack(fill="x", pady=(12, 8))
    progress.start(10)
    set_status("Starting download...")

    def worker():
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in process.stdout:
                line = line.strip()
                if line:
                    set_status(line)
            code = process.wait()
            root.after(0, lambda: finish(code))
        except Exception as exc:
            root.after(0, lambda: finish_error(str(exc)))

    threading.Thread(target=worker, daemon=True).start()

def finish(code):
    progress.stop()
    download_button.configure(state="normal", bg=ACCENT)
    cancel_button.configure(state="disabled")
    if code == 0:
        set_status("Download complete.", "success")
    else:
        set_status("Download failed. Terminal details check karo.", "error")

def finish_error(error):
    progress.stop()
    download_button.configure(state="normal", bg=ACCENT)
    cancel_button.configure(state="disabled")
    set_status("Error: " + error, "error")

def clear_url():
    url_var.set("")
    url_entry.focus_set()
    set_status("Ready.")

root = tk.Tk()
root.title(APP_NAME)
root.configure(bg=BG)
root.geometry("860x680")
root.minsize(780, 620)

# Fonts
FONT = "Segoe UI"

# Top bar
top = tk.Frame(root, bg=BG)
top.pack(fill="x", padx=28, pady=(24, 8))

brand = tk.Frame(top, bg=BG)
brand.pack(side="left")
tk.Label(brand, text="SMF", bg=BG, fg=TEXT, font=(FONT, 18, "bold")).pack(anchor="w")
tk.Label(brand, text="YT DOWNLOADER", bg=BG, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w")

tk.Label(top, text="Desktop Video & Audio Downloader", bg=BG, fg=MUTED,
         font=(FONT, 9)).pack(side="right", pady=8)

# Main card
card = tk.Frame(root, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
card.pack(fill="both", expand=True, padx=28, pady=(8, 28))

inner = tk.Frame(card, bg=PANEL)
inner.pack(fill="both", expand=True, padx=28, pady=26)

tk.Label(inner, text="Download", bg=PANEL, fg=TEXT, font=(FONT, 22, "bold")).pack(anchor="w")
tk.Label(inner, text="Everything you need in one window.", bg=PANEL, fg=MUTED,
         font=(FONT, 10)).pack(anchor="w", pady=(2, 22))

# URL
tk.Label(inner, text="YOUTUBE URL", bg=PANEL, fg=MUTED,
         font=(FONT, 8, "bold")).pack(anchor="w")

url_row = tk.Frame(inner, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
url_row.pack(fill="x", pady=(7, 18))
url_var = tk.StringVar()
url_entry = tk.Entry(url_row, textvariable=url_var, bg=PANEL_2, fg=TEXT,
                     insertbackground=TEXT, relief="flat", bd=0, font=(FONT, 11))
url_entry.pack(side="left", fill="x", expand=True, padx=14, pady=12)
tk.Button(url_row, text="×", command=clear_url, bg=PANEL_2, fg=MUTED,
          activebackground=PANEL_2, activeforeground=TEXT, relief="flat",
          bd=0, font=(FONT, 12), cursor="hand2").pack(side="right", padx=8)

# Mode
tk.Label(inner, text="FORMAT", bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w")
mode_row = tk.Frame(inner, bg=PANEL)
mode_row.pack(fill="x", pady=(7, 18))

mode_var = tk.StringVar(value="Video")
video_btn = tk.Button(mode_row, text="VIDEO", command=lambda: select_mode("Video"),
                      bg=ACCENT, fg=ACCENT_TEXT, relief="flat", bd=0,
                      font=(FONT, 9, "bold"), cursor="hand2", padx=24, pady=11)
video_btn.pack(side="left")

mp3_btn = tk.Button(mode_row, text="MP3 AUDIO", command=lambda: select_mode("MP3"),
                    bg=PANEL_2, fg=TEXT, relief="flat", bd=0,
                    font=(FONT, 9, "bold"), cursor="hand2", padx=20, pady=11)
mp3_btn.pack(side="left", padx=8)

# Quality
tk.Label(inner, text="QUALITY", bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w")
quality_row = tk.Frame(inner, bg=PANEL)
quality_row.pack(fill="x", pady=(7, 18))

quality_var = tk.StringVar(value="1080p")
quality_buttons = []
quality_buttons_map = {}
for label in ["720p", "1080p", "1440p / 2K", "2160p / 4K", "Best"]:
    value = "Best available" if label == "Best" else label
    b = tk.Button(quality_row, text=label,
                  command=lambda v=value: select_quality(v),
                  bg=ACCENT if value == "1080p" else PANEL_2,
                  fg=ACCENT_TEXT if value == "1080p" else TEXT,
                  activebackground=ACCENT, activeforeground=ACCENT_TEXT,
                  relief="flat", bd=0, font=(FONT, 9, "bold"),
                  cursor="hand2", padx=13, pady=9)
    b.pack(side="left", padx=(0, 7))
    quality_buttons.append(b)
    quality_buttons_map[value] = b

# Custom duration
duration_box = tk.Frame(inner, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
duration_box.pack(fill="x", pady=(2, 18), ipady=2)

header = tk.Frame(duration_box, bg=PANEL_2)
header.pack(fill="x", padx=14, pady=(11, 0))
custom_var = tk.BooleanVar(value=False)
tk.Checkbutton(header, text="CUSTOM LENGTH", variable=custom_var, command=toggle_custom,
               bg=PANEL_2, fg=TEXT, selectcolor=PANEL_2, activebackground=PANEL_2,
               activeforeground=TEXT, font=(FONT, 8, "bold")).pack(side="left")
custom_hint = tk.Label(header, text="Full video / full audio", bg=PANEL_2, fg=MUTED,
                       font=(FONT, 8))
custom_hint.pack(side="right")

time_row = tk.Frame(duration_box, bg=PANEL_2)
time_row.pack(fill="x", padx=14, pady=(8, 12))

tk.Label(time_row, text="START", bg=PANEL_2, fg=MUTED, font=(FONT, 8, "bold")).pack(side="left")
start_var = tk.StringVar(value="00:00:00")
start_entry = tk.Entry(time_row, textvariable=start_var, state="disabled",
                       bg=PANEL_2, fg=MUTED, insertbackground=TEXT,
                       disabledbackground=PANEL_2, relief="flat", bd=0, width=13,
                       font=(FONT, 10))
start_entry.pack(side="left", padx=(8, 26))

tk.Label(time_row, text="END", bg=PANEL_2, fg=MUTED, font=(FONT, 8, "bold")).pack(side="left")
end_var = tk.StringVar(value="00:01:00")
end_entry = tk.Entry(time_row, textvariable=end_var, state="disabled",
                     bg=PANEL_2, fg=MUTED, insertbackground=TEXT,
                     disabledbackground=PANEL_2, relief="flat", bd=0, width=13,
                     font=(FONT, 10))
end_entry.pack(side="left", padx=(8, 0))

# Save location
save_row = tk.Frame(inner, bg=PANEL)
save_row.pack(fill="x", pady=(0, 18))
tk.Label(save_row, text="SAVE TO", bg=PANEL, fg=MUTED, font=(FONT, 8, "bold")).pack(anchor="w")
folder_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
save_box = tk.Frame(save_row, bg=PANEL_2, highlightbackground=BORDER, highlightthickness=1)
save_box.pack(fill="x", pady=(7, 0))
tk.Entry(save_box, textvariable=folder_var, bg=PANEL_2, fg=TEXT, insertbackground=TEXT,
         relief="flat", bd=0, font=(FONT, 9)).pack(side="left", fill="x", expand=True, padx=12, pady=10)
tk.Button(save_box, text="BROWSE", command=browse_folder, bg=PANEL_2, fg=TEXT,
          activebackground=PANEL_2, activeforeground=ACCENT, relief="flat", bd=0,
          font=(FONT, 8, "bold"), cursor="hand2").pack(side="right", padx=10)

# Action row
action = tk.Frame(inner, bg=PANEL)
action.pack(fill="x")
download_button = tk.Button(action, text="DOWNLOAD", command=start_download,
                            bg=ACCENT, fg=ACCENT_TEXT, activebackground="#dddddd",
                            activeforeground=ACCENT_TEXT, relief="flat", bd=0,
                            font=(FONT, 10, "bold"), cursor="hand2", padx=24, pady=12)
download_button.pack(side="left", fill="x", expand=True)

cancel_button = tk.Button(action, text="CANCEL", state="disabled",
                          bg=PANEL_2, fg=MUTED, activebackground=PANEL_2,
                          relief="flat", bd=0, font=(FONT, 9, "bold"), padx=18, pady=12)
cancel_button.pack(side="left", padx=(10, 0))

# Status
status_var = tk.StringVar(value="Ready. Paste a YouTube URL to begin.")
status_label = tk.Label(inner, textvariable=status_var, bg=PANEL, fg=MUTED,
                        font=(FONT, 9), anchor="w")
status_label.pack(fill="x", pady=(12, 0))

root.mainloop()
