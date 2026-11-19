#!/usr/bin/env bash
set -e

echo "=================================================="
echo "    INSTALAÇÃO RÁPIDA: QA ONBOARDING AUTOMATION   "
echo "=================================================="

# 1. Verifica Python 3
if ! command -v python3 &> /dev/null; then
    echo "[!] Erro: Python 3 não foi encontrado. Instale Python 3.11 ou superior."
    exit 1
fi

echo "[1/4] Criando ambiente virtual (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "[2/4] Ativando ambiente e instalando dependências..."
source .venv/bin/activate
pip install -r requirements.txt

echo "[3/4] Instalando navegador Chromium do Playwright..."
playwright install chromium

if [ ! -f ".env" ]; then
    echo "[*] Criando arquivo de configuração .env a partir do .env.example..."
    cp .env.example .env
fi

echo "[4/4] Executando diagnóstico de pré-voo..."
python check_env.py

echo ""
echo "=================================================="
echo "[✓] INSTALAÇÃO CONCLUÍDA COM SUCESSO!"
echo "Para executar os testes automatizados: pytest -v"
echo "Para executar o framework: python main.py"
echo "=================================================="

