@echo off
setlocal
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name "SMF_YT_Downloader" --collect-all imageio_ffmpeg app.py
echo.
echo EXE: dist\SMF_YT_Downloader.exe
pause
