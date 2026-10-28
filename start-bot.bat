@echo off
chcp 65001 >nul
title Deadline Bot
rem Always move into this file's own folder, so the bot finds .env and data.json
rem no matter where the script was launched from.
cd /d "%~dp0"
echo Starting the bot... stop it with Ctrl+C or by closing this window.
echo.
".venv\Scripts\python.exe" bot.py
echo.
echo The bot has stopped.
pause
