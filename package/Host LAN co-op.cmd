@echo off
rem Hosts Witcher 3 co-op on the home network: server, your newest save shared with the other player, then the game.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0w3coop.ps1" -Mode host
