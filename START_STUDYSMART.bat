@echo off
title StudySmart Launcher
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_studysmart.ps1"
if errorlevel 1 pause

