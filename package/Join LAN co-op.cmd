@echo off
rem Joins Witcher 3 co-op on the home network: finds the host, copies the host's save to a co-op slot, starts the game.
rem To skip the search: "Join LAN co-op.cmd" 192.168.1.20
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0w3coop.ps1" -Mode join -HostAddress "%~1"
