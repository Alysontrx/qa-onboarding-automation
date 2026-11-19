@echo off
chcp 65001 >nul
title Instalacao QA Automation - Windows
cls

echo ==========================================================
echo    INSTALACAO QA ONBOARDING AUTOMATION (WINDOWS)        
echo ==========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    ) else (
        echo [!] Erro: Python nao encontrado no PATH do Windows.
        echo Baixe e instale o Python 3.11+ marcando "Add Python to PATH".
        pause
        exit /b 1
    )
)

echo [1/4] Criando ambiente virtual (.venv)...
if not exist ".venv" (
    python -m venv .venv
)

echo [2/4] Ativando ambiente e instalando dependencias...
call .venv\Scripts\activate.bat
pip install -r requirements.txt

echo [3/4] Instalando Chromium do Playwright...
playwright install chromium

if not exist ".env" (
    echo [*] Criando arquivo de configuracao .env a partir do .env.example...
    copy .env.example .env >nul
)

echo [4/4] Executando diagnostico de pre-voo...
python check_env.py

echo.
echo ==========================================================
echo [OK] INSTALACAO CONCLUIDA COM SUCESSO!
echo Para executar a automacao, use: iniciar_windows.bat
echo ==========================================================
pause

