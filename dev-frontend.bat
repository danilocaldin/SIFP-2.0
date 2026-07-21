@echo off
set PATH=%PATH%;C:\Program Files\nodejs\
cd /d "%~dp0frontend"
call npm run dev
