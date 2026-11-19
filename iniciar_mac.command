#!/usr/bin/env bash

# Vai para a pasta onde o script está localizado
cd "$(dirname "$0")"

clear
echo "=========================================================="
echo "    SIXTYSIX - QA ONBOARDING AUTOMATION (ADSPOWER)        "
echo "=========================================================="
echo ""

# Se o ambiente virtual não existir, roda a instalação automática
if [ ! -d ".venv" ]; then
    echo "[*] Ambiente virtual não detectado. Executando setup inicial..."
    bash setup.sh
fi

# Ativa o ambiente virtual
source .venv/bin/activate

# Exibe diagnóstico rápido
python check_env.py
echo ""

echo "Como você deseja executar hoje?"
echo "  [1] Rodar com ADSPOWER (Recomendado - Perfis Reais)"
echo "  [2] Rodar LOCAL (Playwright Standalone)"
echo "  [3] Sincronizar perfis do AdsPower para o usuarios.csv"
echo ""
read -p "Digite a opção desejada [1]: " OPCAO
OPCAO=${OPCAO:-1}

echo ""
if [ "$OPCAO" = "1" ]; then
    echo "[*] Iniciando automação com AdsPower..."
    python main.py --use-adspower --concurrency 2
elif [ "$OPCAO" = "2" ]; then
    echo "[*] Iniciando automação em modo Local..."
    python main.py --local --no-headless
elif [ "$OPCAO" = "3" ]; then
    echo "[*] Consultando perfis na Local API do AdsPower e gerando CSV..."
    python listar_perfis_adspower.py --sync-csv
fi

echo ""
echo "=========================================================="
echo "Execução finalizada. Verifique o Discord (#relatorios-qa)!"
echo "=========================================================="
read -p "Pressione [ENTER] para fechar..."

