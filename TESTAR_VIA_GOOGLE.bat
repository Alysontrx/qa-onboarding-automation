@echo off
chcp 65001 >nul
title TESTE VIA GOOGLE - SIXTYSIX GATEWAY
echo ==================================================================
echo   TESTE 1 CONTA VIA GOOGLE (SEM PROXY) + REMIX + CLAUDE OPUS
echo ==================================================================
echo.
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py"
) else (
    set "PY_CMD=python"
)
%PY_CMD% -u criar_e_testar_google.py
echo.
echo ==================================================================
echo Pressione qualquer tecla para fechar...
pause >nul
