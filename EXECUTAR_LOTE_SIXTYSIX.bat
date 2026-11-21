@echo off
chcp 65001 >nul
cd /d "%~dp0"
title OPERACAO SIXTYSIX 100%% AUTOMATIZADA
echo ==================================================================
echo   OPERACAO SIXTYSIX - CRIACAO + REMIX + AUTO-REGISTRO NO CLAUDE
echo   Dominios: @emporioburguers.shop - @destravacreditoquiz.com.br - Matriz: 448b5334-3b25-4ed6-9e4d-b6ce9035dd07
echo ==================================================================
echo.
echo Iniciando automacao oficial com auto-registro...
where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py -3"
) else (
    set "PY_CMD=python"
)
%PY_CMD% -u fluxo_lote_sixtysix.py 1 3
echo.
echo ==================================================================
echo Processo finalizado! Pressione qualquer tecla para sair...
pause
