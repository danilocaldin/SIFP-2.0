@echo off
REM So mexe no PATH se "npm" ainda nao resolver sozinho (ex: Node instalado
REM na mesma sessao que iniciou este processo, antes do PATH global
REM propagar). Em qualquer maquina com Node instalado normalmente, este
REM bloco nao faz nada.
where npm >nul 2>nul
if errorlevel 1 (
    if exist "C:\Program Files\nodejs\npm.cmd" (
        set "PATH=%PATH%;C:\Program Files\nodejs\"
    )
)
cd /d "%~dp0frontend"
call npm run dev
