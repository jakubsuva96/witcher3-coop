@echo off
rem Hosts a Witcher 3 co-op game on the home network (LAN): starts the server on this PC, no Steam relay.
rem Players on the same network find it by themselves with "Join LAN co-op.cmd".
setlocal
cd /d "%~dp0"
where java >nul 2>&1 || (
  echo Hosting needs Java 21 or newer: https://adoptium.net
  echo Install it, then run this again. The player who joins doesn't need Java.
  pause
  exit /b 1
)
set "NAME=%USERNAME%"
if exist name.txt set /p NAME=<name.txt
set "INPUT="
set /p INPUT=Your name in the game [%NAME%]:
if defined INPUT set "NAME=%INPUT%"
>name.txt echo %NAME%
(
  echo ^<?xml version="1.0"?^>
  echo ^<Config^>
  echo 	^<Username^>%NAME%^</Username^>
  echo 	^<ServerIP^>127.0.0.1^</ServerIP^>
  echo 	^<Port^>40000^</Port^>
  echo ^</Config^>
) >"..\WitcherOnline\config.xml"
echo.
echo This PC's addresses on the network (the other player can also type one into config.xml):
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | ForEach-Object { '  ' + $_.IPAddress + '  (' + $_.InterfaceAlias + ')' }"
echo.
echo If Windows asks whether Java may use the network, allow it on Private networks.
echo (UDP 40000: the game; TCP 40003: crash reports from the other PC land in server\crash-reports.)
echo.
echo Keep this window open while you play. Start The Witcher 3 and load a save.
echo The other player runs "Join LAN co-op.cmd". Close this window to end the session.
echo.
java -jar "%~dp0server\WitcherServer.jar" 40000
pause
