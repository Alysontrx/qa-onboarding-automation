#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# SIXTYSIX USINA MÓVEL 4G - ATALHO 1-CLIQUE PARA O CELULAR (TERMUX)
# ==============================================================================
# 100% Autônomo no Celular - Sem PC e Sem Cabos
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$DIR/iniciar_usina_celular.sh" ]; then
    bash "$DIR/iniciar_usina_celular.sh" "$@"
    exit $?
fi

if [ -f "$DIR/fluxo_lote_sixtysix.py" ]; then
    export MODO_CELULAR=1
    export USE_PROXY_4G=0
    python3 "$DIR/fluxo_lote_sixtysix.py" 0
    exit $?
fi

echo "Arquivo fluxo_lote_sixtysix.py não encontrado na pasta atual ($DIR)."
echo "Execute: bash iniciar_usina_celular.sh"
