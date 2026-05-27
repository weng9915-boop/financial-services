@echo off
:: eToro Trading Bot — Windows launcher
:: Double-click to run manually, or let Task Scheduler call this file.
:: Credentials are loaded from .env in the repo root automatically.

:: Change to the repo root (two levels up from this script's location)
cd /d "%~dp0..\..\..\.."

:: Create logs folder if it doesn't exist
if not exist "logs" mkdir logs

:: Run the bot and append output to a dated log file
echo [%date% %time%] Starting eToro bot... >> logs\bot.log
python plugins\partner-built\etoro\scripts\run_bot.py %* >> logs\bot.log 2>&1
echo [%date% %time%] Bot finished (exit code %errorlevel%). >> logs\bot.log
