#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# ⚡ SIXTYSIX - USINA MÓVEL 4G (100% NO CELULAR VIA TERMUX)
# ==============================================================================
# Execução direta no aparelho Android usando os dados móveis nativos (4G Claro/Vivo).
# NÃO precisa de computador. NÃO precisa de cabo USB.
# Loop Contínuo 24/7 com Rotação Automática de Domínios.
# ==============================================================================

# Se estiver no bash padrão Linux/Android, garante diretório do script
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Cores
VERDE="\033[1;32m"
CIANO="\033[1;36m"
AMARELO="\033[1;33m"
VERMELHO="\033[1;31m"
RESET="\033[0m"

clear
echo -e "${VERDE}================================================================${RESET}"
echo -e "${VERDE}       ⚡ SIXTYSIX - USINA MÓVEL 4G (MOTO G22 / TERMUX) ⚡       ${RESET}"
echo -e "${VERDE}================================================================${RESET}"
echo -e "${CIANO}📱 Execução 100% Autônoma no Celular (Sem PC e Sem Cabos)${RESET}"
echo -e "${CIANO}🌐 Rotação Ativa de Domínios Catch-All contra bloqueios:${RESET}"
echo -e "   1. @emporioburguers.shop"
echo -e "   2. @destravacreditoquiz.com.br"
echo -e "   3. @sixtysix.online"
echo -e "${AMARELO}🔄 Modo: CONTÍNUO 24/7 (Cria contas sem parar em loop infinito)${RESET}"
echo -e "${VERMELHO}🛑 Como parar: Pressione [CTRL + C] a qualquer momento${RESET}"
echo -e "${VERDE}================================================================${RESET}"
echo ""

# 1. Verifica dependências essenciais
echo -e "${CIANO}[1/3] Verificando ambiente Python e pacotes no celular...${RESET}"
if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
    echo -e "${AMARELO}Instalando Python no Termux...${RESET}"
    pkg update -y && pkg install -y python python-pip
fi

PYTHON_CMD="python3"
if ! command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python"
fi

# Instala httpx se necessário
$PYTHON_CMD -c "import httpx" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${AMARELO}Instalando biblioteca httpx...${RESET}"
    pip install httpx
fi

# Instala playwright para Termux se necessário
$PYTHON_CMD -c "import playwright" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${AMARELO}Configurando Playwright e Chromium para Termux (aguarde alguns segundos)...${RESET}"
    curl -sL https://raw.githubusercontent.com/uno-km/amv-playwright/main/install.sh | bash
fi

# 2. Configura variáveis de ambiente para execução direta no aparelho
export MODO_CELULAR=1
export USE_PROXY_4G=0
export HEADLESS=1

echo -e "${VERDE}[OK] Ambiente pronto!${RESET}"
echo ""

# 3. Inicia Usina em Modo Contínuo 24/7
echo -e "${CIANO}[2/3] Testando conexão de dados móveis 4G nativa...${RESET}"
IP_TESTE=$(curl -s --connect-timeout 4 http://ip-api.com/line?fields=query,isp || echo "4G Conectado")
echo -e "${VERDE}📶 Conexão: $IP_TESTE${RESET}"
echo ""

echo -e "${VERDE}[3/3] DISPARANDO CRIAÇÃO CONTÍNUA 24/7...${RESET}"
echo -e "${AMARELO}⚡ O robô criará contas sem parar alternando os domínios.${RESET}"
echo -e "${AMARELO}⚡ Notificações verdes serão enviadas no Discord a cada sucesso.${RESET}"
echo -e "${VERMELHO}🛑 Para interromper a criação a qualquer momento: aperte CTRL + C${RESET}"
echo ""
sleep 1

# Executa fluxo_lote_sixtysix em modo contínuo (argumento 0 = loop infinito)
$PYTHON_CMD fluxo_lote_sixtysix.py 0

echo ""
echo -e "${VERDE}================================================================${RESET}"
echo -e "${VERDE}Sessão da Usina Móvel finalizada.${RESET}"
echo -e "As contas criadas estão salvas em: ${CIANO}accounts/contas_criadas.txt${RESET}"
echo -e "${VERDE}================================================================${RESET}"

