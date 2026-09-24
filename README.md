# SMF YT Downloader

Windows desktop downloader for authorized downloads.

## Features
- 720p, 1080p, 1440p/2K, 2160p/4K and best available
- MP3 extraction
- Full video/audio
- Custom start/end range
- MP4 output
- Simple Windows GUI

## Development
Python 3.11+ and FFmpeg are required.

```bat
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
python app.py
```

## Build
Run `build_exe.bat`. GitHub Actions also builds the Windows installer.

The maximum resolution depends on the source video's available formats.
Use only content you have permission to download and comply with YouTube's terms and applicable copyright law.
