#!/usr/bin/env bash
# ==============================================================================
# SIXTYSIX AI - INICIADOR 1-CLIQUE DA USINA MÓVEL 4G
# ==============================================================================

# Entra na pasta do script
cd "$(dirname "$0")"

# Adiciona caminhos do ADB e binários locais ao PATH
export PATH="/home/alysontrx/Android/Sdk/platform-tools:$HOME/.local/bin:$PATH"

# Cores ANSI
GREEN='\033[1;32m'
CYAN='\033[1;36m'
YELLOW='\033[1;33m'
WHITE='\033[1;37m'
BOLD='\033[1m'
NC='\033[0m'

clear
echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}       ⚡ USINA MÓVEL 4G SIXTYSIX - CRIADOR AUTÔNOMO DE CONTAS ⚡     ${NC}"
echo -e "${GREEN}==================================================================${NC}"
echo ""

# 1. Verifica ou ativa o ambiente Python (.venv)
if [ -d ".venv" ]; then
    PYTHON_CMD="./.venv/bin/python3"
else
    PYTHON_CMD="python3"
fi

# 2. Diagnóstico do celular Moto G22 via ADB
echo -e "${CYAN}[1/3] Verificando aparelho 4G Moto G22 (ADB)...${NC}"
DEVICE_FOUND=$(adb devices 2>/dev/null | grep -w "device" | grep -v "List" || true)
if [ -n "$DEVICE_FOUND" ]; then
    echo -e "      ${GREEN}✔ Moto G22 conectado e pronto com rotação de IP!${NC}"
    adb forward tcp:8080 tcp:8080 2>/dev/null || true
else
    echo -e "      ${YELLOW}⚠ Moto G22 não detectado via USB. Usando IP direto da rede.${NC}"
fi

# 3. Verifica servidor SixtySix local (porta 3000)
echo -e "${CYAN}[2/3] Verificando Painel SixtySix (porta 3000)...${NC}"
if curl -s http://127.0.0.1:3000/api/health >/dev/null 2>&1; then
    echo -e "      ${GREEN}✔ Painel SixtySix ONLINE: http://localhost:3000/dashboard?demo=1&aba=pool${NC}"
else
    echo -e "      ${YELLOW}ℹ Iniciando servidor web SixtySix em segundo plano...${NC}"
    export PATH="$HOME/.local/bin:$PATH"
    (cd sixtyosix && HOST=0.0.0.0 PORT=3000 node --experimental-strip-types --import ./scripts/test-register.mjs server/start.ts >/dev/null 2>&1 &)
    sleep 2
    echo -e "      ${GREEN}✔ Servidor ativo em http://localhost:3000!${NC}"
fi

# 4. Domínios Catch-All configurados
echo -e "${CYAN}[3/3] Domínios Catch-All Ativos para Rotação:${NC}"
if [ -f "config/dominios_catchall.txt" ]; then
    grep -v "^#" config/dominios_catchall.txt | grep -v "^$" | while read -r dom; do
        echo -e "      ${GREEN}• @$dom${NC}"
    done
fi

echo ""
echo -e "${GREEN}==================================================================${NC}"
echo -e "${BOLD}  Pronto para criar contas e injetar tokens de IA no pool!${NC}"
echo -e "${GREEN}==================================================================${NC}"
echo ""
echo -e "${WHITE}Modo de Execução da Usina:${NC}"
echo -e "  Pressione ${GREEN}[ENTER]${NC} para ${BOLD}MODO CONTÍNUO 24/7 (Só para quando desconectar o celular)${NC}"
echo -e "  Ou digite um lote específico (ex: 10, 20, 50)"
echo ""
read -p "Sua escolha [0 = Contínuo]: " QUANTIDADE
QUANTIDADE=${QUANTIDADE:-0}

echo ""
if [ "$QUANTIDADE" = "0" ]; then
    echo -e "${GREEN}🚀 INICIANDO MODO CONTÍNUO 24/7 (ROTAÇÃO CIRCULAR DE DOMÍNIOS ATIVA)...${NC}"
    echo -e "Para parar: ${YELLOW}Basta desconectar o cabo USB do celular ou pressionar Ctrl+C.${NC}"
else
    echo -e "${GREEN}🚀 INICIANDO CRIAÇÃO DE $QUANTIDADE CONTA(S) AGORA...${NC}"
fi
echo -e "Acompanhe ao vivo pelo painel admin: ${CYAN}http://localhost:3000/adminxv1?demo=1${NC}"
echo "------------------------------------------------------------------"
echo ""

$PYTHON_CMD fluxo_lote_sixtysix.py "$QUANTIDADE"

echo ""
echo -e "${GREEN}==================================================================${NC}"
echo -e "${GREEN}✅ OPERAÇÃO CONCLUÍDA!${NC}"
echo -e "As contas e tokens criados já estão disponíveis no Painel SixtySix."
echo -e "${GREEN}==================================================================${NC}"
echo ""
read -p "Pressione [ENTER] para sair..."
