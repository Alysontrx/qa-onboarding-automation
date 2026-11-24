"""Módulo de Gerenciamento e Rotação do Proxy 4G Móvel via Celular Android (ADB).

Permite:
- Redirecionar a porta 8080 via ADB forward;
- Obter IP público atual da conexão de dados móveis (Claro, Vivo, TIM);
- Rotacionar o IP público automaticamente ligando e desligando o Modo Avião via ADB.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("proxy_4g")

# Caminhos do ADB
ADB_CANDIDATOS = [
    Path("/home/alysontrx/Android/Sdk/platform-tools/adb"),
    Path("adb"),
]


def _obter_adb_cmd() -> str:
    for cand in ADB_CANDIDATOS:
        if cand.is_file() and os.access(cand, os.X_OK):
            return str(cand)
    return "adb"


import os

ADB_BIN = _obter_adb_cmd()
PROXY_URL = "http://127.0.0.1:8080"


def garantir_adb_forward(porta: int = 8080) -> bool:
    """Garante que a porta do Every Proxy no Android esteja mapeada no localhost do PC."""
    if os.environ.get("MODO_CELULAR") == "1" or os.environ.get("USE_PROXY_4G") == "0":
        return True

    try:
        res = subprocess.run(
            [ADB_BIN, "forward", f"tcp:{porta}", f"tcp:{porta}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            logger.debug("ADB forward tcp:%d tcp:%d garantido.", porta, porta)
            return True
        logger.warning("Falha no adb forward: %s", res.stderr)
        return False
    except Exception as exc:
        logger.error("Erro ao executar adb forward: %s", exc)
        return False


def obter_ip_atual(timeout: float = 8.0, usar_proxy: bool = True) -> Optional[dict]:
    """Obtém o IP público atual e dados de operadora (via proxy 4G ou conexão direta no celular)."""
    # Se usar_proxy estiver ativo, tenta primeiro via Every Proxy
    if usar_proxy and PROXY_URL:
        try:
            with httpx.Client(proxy=PROXY_URL, timeout=timeout) as client:
                r = client.get("http://ip-api.com/json/")
                if r.status_code == 200:
                    data = r.json()
                    logger.info(
                        "📱 [PROXY 4G] IP: %s | Operadora: %s (%s, %s)",
                        data.get("query"),
                        data.get("isp"),
                        data.get("city"),
                        data.get("countryCode"),
                    )
                    return data
        except Exception:
            pass

    # Fallback / Modo Direto no Celular (dados móveis nativos 4G)
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get("http://ip-api.com/json/")
            if r.status_code == 200:
                data = r.json()
                logger.info(
                    "📱 [4G CELULAR] IP: %s | Operadora: %s (%s, %s)",
                    data.get("query"),
                    data.get("isp"),
                    data.get("city"),
                    data.get("countryCode"),
                )
                return data
    except Exception as exc:
        logger.warning("Não foi possível checar IP atual: %s", exc)
    return None


def rotacionar_ip_4g(espera_aviao: float = 4.0, espera_reconectar: float = 6.0) -> Optional[str]:
    """Alterna o Modo Avião (via ADB se no PC ou via Termux/notificação se no celular) e retorna o novo IP público."""
    is_celular = os.environ.get("MODO_CELULAR") == "1" or os.environ.get("USE_PROXY_4G") == "0"
    
    if is_celular:
        logger.info("✈️ [4G CELULAR] Para renovar o IP 4G no aparelho: baixe a barra e ligue/desligue o Modo Avião por 3 segundos.")
        info = obter_ip_atual(usar_proxy=False)
        return info.get("query") if info else None

    logger.info("✈️ [PROXY 4G] Alternando Modo Avião no celular via ADB...")
    try:
        # Ativa Modo Avião
        subprocess.run(
            [ADB_BIN, "shell", "cmd", "connectivity", "airplane-mode", "enable"],
            capture_output=True,
            timeout=5,
        )
        time.sleep(espera_aviao)

        # Desativa Modo Avião
        subprocess.run(
            [ADB_BIN, "shell", "cmd", "connectivity", "airplane-mode", "disable"],
            capture_output=True,
            timeout=5,
        )
        time.sleep(espera_reconectar)

        garantir_adb_forward()
        info = obter_ip_atual()
        if info and info.get("query"):
            novo_ip = info["query"]
            logger.info("🎉 [PROXY 4G] IP renovado com sucesso: %s (%s)", novo_ip, info.get("isp"))
            return novo_ip
    except Exception as exc:
        logger.error("Falha ao rotacionar IP via ADB: %s", exc)

    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    garantir_adb_forward()
    ip_antes = obter_ip_atual()
    print("IP Antes:", ip_antes)
    print("\nRotacionando...")
    novo_ip = rotacionar_ip_4g()
    print("Novo IP:", novo_ip)
