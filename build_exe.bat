@echo off
echo ============================================
echo   JJS Piano Bot — Building Windows .exe
echo ============================================
echo.

REM Install dependencies
echo [1/3] Installing dependencies...
pip install pydirectinput pyinstaller
echo.

REM Build
echo [2/3] Building executable...
pyinstaller --onefile --noconsole --name "JJS_Piano_Bot" jjs_piano_gui.py
echo.

echo [3/3] Done!
echo.
echo   Your .exe is at:  dist\JJS_Piano_Bot.exe
echo.
echo   Copy it anywhere and run — no Python needed!
echo.
pause
