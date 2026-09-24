import os, shutil, subprocess, sys, threading, tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_NAME = "SMF YT Downloader"

def which(name):
    return shutil.which(name) or shutil.which(name + ".exe")

def set_status(text):
    root.after(0, lambda: status.set(text[-140:]))

def choose_folder():
    p = filedialog.askdirectory()
    if p:
        folder.set(p)

def toggle_range():
    state = "normal" if range_enabled.get() else "disabled"
    start_entry.configure(state=state)
    end_entry.configure(state=state)

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

    if range_enabled.get():
        s = start.get().strip() or "00:00:00"
        e = end.get().strip()
        if not e:
            raise ValueError("End time is required for a custom range.")
        cmd += ["--download-sections", f"*{s}-{e}", "--force-keyframes-at-cuts"]

    template = os.path.join(folder.get(), "%(title)s.%(ext)s")
    cmd += ["-o", template, url]
    return cmd

def start_download():
    url = url_var.get().strip()
    if not url:
        messagebox.showerror(APP_NAME, "YouTube URL daalo.")
        return
    if not os.path.isdir(folder.get()):
        messagebox.showerror(APP_NAME, "Valid save folder select karo.")
        return
    if not which("ffmpeg"):
        messagebox.showerror(APP_NAME, "FFmpeg missing hai. Installer/setup me FFmpeg available hona chahiye.")
        return
    try:
        cmd = build_command(url)
    except Exception as e:
        messagebox.showerror(APP_NAME, str(e))
        return

    download_btn.configure(state="disabled")
    progress.start(10)
    set_status("Starting...")

    def worker():
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace")
            for line in p.stdout:
                line=line.strip()
                if line:
                    set_status(line)
            code=p.wait()
            root.after(0, lambda: finish(code))
        except Exception as e:
            root.after(0, lambda: fail(str(e)))

    threading.Thread(target=worker, daemon=True).start()

def finish(code):
    progress.stop()
    download_btn.configure(state="normal")
    if code == 0:
        status.set("Download complete.")
        messagebox.showinfo(APP_NAME, "Download complete.")
    else:
        status.set("Download failed.")
        messagebox.showerror(APP_NAME, "Download failed. Details console/log output me milenge.")

def fail(error):
    progress.stop()
    download_btn.configure(state="normal")
    status.set("Error.")
    messagebox.showerror(APP_NAME, error)

root=tk.Tk()
root.title(APP_NAME)
root.geometry("760x590")
root.minsize(680,520)

style=ttk.Style()
try: style.theme_use("vista")
except tk.TclError: pass

main=ttk.Frame(root,padding=26)
main.pack(fill="both",expand=True)

ttk.Label(main,text="SMF YT Downloader",font=("Segoe UI",24,"bold")).pack(anchor="w")
ttk.Label(main,text="720p • 1080p • 2K • 4K • MP3 • Full length • Custom clips",
          font=("Segoe UI",10)).pack(anchor="w",pady=(2,22))

ttk.Label(main,text="YouTube URL").pack(anchor="w")
url_var=tk.StringVar()
ttk.Entry(main,textvariable=url_var,font=("Segoe UI",11)).pack(fill="x",pady=(5,18))

grid=ttk.Frame(main); grid.pack(fill="x")
ttk.Label(grid,text="Type").grid(row=0,column=0,sticky="w")
ttk.Label(grid,text="Quality").grid(row=0,column=1,sticky="w",padx=(22,0))
mode_var=tk.StringVar(value="Video")
quality_var=tk.StringVar(value="1080p")
ttk.Combobox(grid,textvariable=mode_var,state="readonly",values=["Video","MP3"],width=24).grid(row=1,column=0,sticky="w",pady=(5,16))
ttk.Combobox(grid,textvariable=quality_var,state="readonly",
             values=["720p","1080p","1440p / 2K","2160p / 4K","Best available"],
             width=24).grid(row=1,column=1,sticky="w",padx=(22,0),pady=(5,16))

range_enabled=tk.BooleanVar(value=False)
ttk.Checkbutton(main,text="Custom length",variable=range_enabled,command=toggle_range).pack(anchor="w",pady=(0,8))

times=ttk.Frame(main); times.pack(fill="x")
ttk.Label(times,text="Start  HH:MM:SS").grid(row=0,column=0,sticky="w")
ttk.Label(times,text="End  HH:MM:SS").grid(row=0,column=1,sticky="w",padx=(22,0))
start=tk.StringVar(value="00:00:00")
end=tk.StringVar(value="00:01:00")
start_entry=ttk.Entry(times,textvariable=start,width=25,state="disabled")
end_entry=ttk.Entry(times,textvariable=end,width=25,state="disabled")
start_entry.grid(row=1,column=0,sticky="w",pady=(5,18))
end_entry.grid(row=1,column=1,sticky="w",padx=(22,0),pady=(5,18))

ttk.Label(main,text="Save to").pack(anchor="w")
folder=tk.StringVar(value=os.path.join(os.path.expanduser("~"),"Downloads"))
fr=ttk.Frame(main); fr.pack(fill="x",pady=(5,20))
ttk.Entry(fr,textvariable=folder).pack(side="left",fill="x",expand=True)
ttk.Button(fr,text="Browse",command=choose_folder).pack(side="left",padx=(8,0))

download_btn=ttk.Button(main,text="DOWNLOAD",command=start_download)
download_btn.pack(fill="x",ipady=9)

progress=ttk.Progressbar(main,mode="indeterminate")
progress.pack(fill="x",pady=(18,8))
status=tk.StringVar(value="Ready.")
ttk.Label(main,textvariable=status).pack(anchor="w")

ttk.Label(main,text="Use only for content you own or are authorized to download.",
          font=("Segoe UI",8)).pack(anchor="w",pady=(20,0))

root.mainloop()
