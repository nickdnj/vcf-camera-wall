@echo off
REM VCF Camera Wall - Windows launcher.
REM Double-click. Starts the local server and opens the wall fullscreen (kiosk)
REM in Edge or Chrome if available, else the default browser.
setlocal
set PORT=8770
set URL=http://localhost:%PORT%/index.html
set DIR=%~dp0

REM Find Python
where python >nul 2>nul && (set PY=python) || (
  where py >nul 2>nul && (set PY=py) || (
    echo Python 3 not found. Install it from python.org, or open src\index.html directly.
    pause
    exit /b 1
  )
)

REM Start the server in a new window
start "VCF Camera Wall server" %PY% "%DIR%serve.py" --port %PORT%
timeout /t 2 /nobreak >nul

REM Try Edge (built into Windows) in kiosk, then Chrome, then default browser
set EDGE="%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
set CHROME="%ProgramFiles%\Google\Chrome\Application\chrome.exe"
set CHROME86="%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

if exist %EDGE% (
  start "" %EDGE% --kiosk %URL% --edge-kiosk-type=fullscreen --no-first-run
) else if exist %CHROME% (
  start "" %CHROME% --kiosk --start-fullscreen --incognito %URL%
) else if exist %CHROME86% (
  start "" %CHROME86% --kiosk --start-fullscreen --incognito %URL%
) else (
  start "" %URL%
)

echo Camera wall running at %URL%
echo Close the server window to stop.
endlocal
