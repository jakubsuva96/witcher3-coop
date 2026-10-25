@echo off
rem Joins a Witcher 3 co-op game hosted on the same home network (LAN). The game finds the host by itself;
rem to skip the search, pass the host's address: "Join LAN co-op.cmd" 192.168.1.20
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
(
  echo ^<?xml version="1.0"?^>
  echo ^<Config^>
  echo 	^<Username^>%NAME%^</Username^>
  echo 	^<ServerIP^>%HOST%^</ServerIP^>
  echo 	^<Port^>40000^</Port^>
  echo ^</Config^>
) >"..\WitcherOnline\config.xml"
echo.
if "%HOST%"=="auto" (
  echo Done. Start The Witcher 3 and load a save: the game looks for the host on the network
  echo for up to 3 minutes, so the host can start a little later.
) else (
  echo Done. Start The Witcher 3 and load a save: the game connects to %HOST%.
)
echo If this game crashes, its crash report goes to the host's PC the next time you connect.
echo.
pause
