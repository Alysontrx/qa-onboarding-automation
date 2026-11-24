#!/data/data/com.termux/files/usr/bin/bash
clear
echo "========================================================"
echo "   ⚡ INSTALANDO USINA MÓVEL SIXTYSIX NO TERMUX ⚡     "
echo "========================================================"
echo "[1/3] Instalando pacotes básicos (curl, unzip, python)..."
pkg update -y >/dev/null 2>&1
pkg install -y curl unzip python >/dev/null 2>&1

echo "[2/3] Baixando arquivos do robô..."
mkdir -p ~/usina
curl -sL https://litter.catbox.moe/3fyxng.zip -o ~/usina.zip
unzip -o ~/usina.zip -d ~/usina >/dev/null 2>&1
rm -f ~/usina.zip

echo "[3/3] Instalando Playwright e Chromium para Termux..."
pip install httpx >/dev/null 2>&1
curl -sL https://raw.githubusercontent.com/uno-km/amv-playwright/main/install.sh | bash

echo ""
echo "✅ Instalação concluída com sucesso!"
echo "Iniciando a Usina Móvel 24/7..."
echo ""
sleep 1
cd ~/usina
bash iniciar_usina_celular.sh

