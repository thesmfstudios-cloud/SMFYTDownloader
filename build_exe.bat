@echo off
setlocal
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "SMF_YT_Downloader" app.py
echo.
echo EXE: dist\\SMF_YT_Downloader.exe
pause
