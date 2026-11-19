@echo off
chcp 65001 >nul
title SixtySix - QA Onboarding Automation
cls

echo ==========================================================
echo     SIXTYSIX - QA ONBOARDING AUTOMATION (WINDOWS)        
echo ==========================================================
echo.

:: Se o ambiente virtual não existir, instala automaticamente
if not exist ".venv" (
    echo [*] Ambiente virtual nao detectado. Realizando instalacao inicial...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
    playwright install chromium
    if not exist ".env" (
        copy .env.example .env >nul
    )
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo [*] Executando diagnostico de ambiente...
python check_env.py
echo.

echo ==========================================================
echo Como voce deseja executar hoje?
echo   [1] Rodar com ADSPOWER (Perfis Reais)
echo   [2] Rodar LOCAL (Playwright Standalone)
echo   [3] Sincronizar perfis do AdsPower para o usuarios.csv
echo ==========================================================
set /p OPCAO="Digite a opcao desejada [1]: "
if "%OPCAO%"=="" set OPCAO=1

echo.
if "%OPCAO%"=="1" (
    echo [*] Iniciando automacao com AdsPower...
    python main.py --use-adspower --concurrency 2
)
if "%OPCAO%"=="2" (
    echo [*] Iniciando automacao em modo Local...
    python main.py --local --no-headless
)
if "%OPCAO%"=="3" (
    echo [*] Consultando perfis na Local API do AdsPower e gerando CSV...
    python listar_perfis_adspower.py --sync-csv
)

echo.
echo ==========================================================
echo Execucao finalizada. Verifique o Discord (#relatorios-qa)!
echo ==========================================================
pause

