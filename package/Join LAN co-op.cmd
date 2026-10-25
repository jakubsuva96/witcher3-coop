@echo off
rem Joins a Witcher 3 co-op game hosted on the same home network (LAN). Run it after the host started
rem "Host LAN co-op.cmd": it finds the host, fetches the host's newest save and sets up a separate co-op profile
rem (your own settings and saves stay untouched). To skip the search, pass the host's address:
rem   "Join LAN co-op.cmd" 192.168.1.20
setlocal
cd /d "%~dp0"
set "NAME=%USERNAME%"
if exist name.txt set /p NAME=<name.txt
set "INPUT="
set /p INPUT=Your name in the game [%NAME%]:
if defined INPUT set "NAME=%INPUT%"
>name.txt echo %NAME%
set "HOST=auto"
if not "%~1"=="" set "HOST=%~1"
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lan-join.ps1" -Name "%NAME%" -HostAddress "%HOST%"
echo.
echo Start The Witcher 3 now. At the main menu it loads the host's save by itself and joins the host's party.
echo Ctrl+F9 in game turns shared enemies and quests off and on.
echo If this game crashes, its crash report goes to the host's PC the next time you connect.
echo.
pause
