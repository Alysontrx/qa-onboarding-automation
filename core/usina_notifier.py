"""Módulo de Notificação Instantânea (Discord) e Telemetria Web para a Usina 4G Móvel.

- Envia notificações detalhadas (cards verde/vermelho) no canal do Discord via Webhook;
- Envia heartbeat com métricas ao vivo para o painel web da SixtySix (/api/usina-heartbeat);
- Recebe comandos remotos do painel web (Pausar, Criar +X, Trocar IP).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
import json
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger("usina_notifier")

DEFAULT_DISCORD_WEBHOOK = os.getenv(
    "DISCORD_WEBHOOK_URL",
    "https://discord.com/api/webhooks/1572780922586144801/FYgYdd0_G1pfnddYJoUHNwr0ytvPRfybfcvffymXdZxyTKJuMWT8KB-G0u7ojQOFczDU",
)
DEFAULT_SIXTYSIX_API = os.getenv("SIXTYSIX_API_URL", "http://127.0.0.1:3000")

BASE_DIR = Path(__file__).resolve().parent.parent
CONTAS_DB_FILE = BASE_DIR / "accounts" / "contas_db.json"


def salvar_conta_local(conta: dict) -> None:
    """Salva a nova conta no banco de dados local accounts/contas_db.json de forma persistente."""
    try:
        CONTAS_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        contas = []
        if CONTAS_DB_FILE.exists():
            try:
                contas = json.loads(CONTAS_DB_FILE.read_text(encoding="utf-8")) or []
            except Exception:
                contas = []

        # Evita duplicatas pelo email ou bridge_url
        email_novo = (conta.get("email") or "").strip().lower()
        bridge_nova = (conta.get("bridge_url") or "").strip()
        contas = [c for c in contas if c.get("email", "").lower() != email_novo and c.get("bridge_url") != bridge_nova]

        # Insere a nova conta no topo
        conta["id"] = 1
        for idx, c in enumerate(contas, 2):
            c["id"] = idx
        contas.insert(0, conta)

        CONTAS_DB_FILE.write_text(json.dumps(contas, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("💾 [BANCO DE DADOS] Conta %s (%s) salva em %s", email_novo, conta.get("token", ""), CONTAS_DB_FILE)
    except Exception as exc:
        logger.warning("Falha ao salvar conta no JSON local: %s", exc)


def notificar_discord_sucesso(
    email: str,
    tempo_segundos: float,
    bridge_url: str,
    projeto_id: str,
    placar_ok: int,
    placar_fail: int,
    operadora: str = "Claro S.A.",
    ip: str = "4G Móvel",
    webhook_url: Optional[str] = None,
) -> bool:
    """Envia card visual verde no Discord confirmando nova conta criada e ponte ativa."""
    url = webhook_url or DEFAULT_DISCORD_WEBHOOK
    if not url:
        return False

    subdominio = bridge_url.replace("https://", "").split("/")[0]
    dominio = email.split("@")[1] if "@" in email else "catch-all"

    payload = {
        "embeds": [
            {
                "title": f"✅ [Nova Conta 4G] {email}",
                "description": (
                    f"**Ponte implantada e registrada com sucesso no SixtySix Gateway!**\n"
                    f"⚡ **Tempo de Execução:** `{tempo_segundos:.1f}s`\n"
                    f"🌐 **Endereço da Ponte:** `{subdominio}`\n"
                    f"🆔 **Projeto ID:** `{projeto_id}`"
                ),
                "color": 0x10B981,  # Emerald / Verde
                "fields": [
                    {"name": "📱 Aparelho & Rede", "value": f"Moto G22 • {operadora}", "inline": True},
                    {"name": "📶 IP Público 4G", "value": f"`{ip}`", "inline": True},
                    {"name": "🌐 Domínio Usado", "value": f"`@{dominio}`", "inline": True},
                    {
                        "name": "📊 Placar da Usina",
                        "value": f"**{placar_ok} Sucesso(s)** / {placar_fail} Falha(s)",
                        "inline": True,
                    },
                ],
                "footer": {
                    "text": f"SixtySix AI 4G Farm • {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                },
            }
        ]
    }

    try:
        r = httpx.post(url, json=payload, timeout=8.0)
        return r.status_code in (200, 204)
    except Exception as exc:
        logger.warning("Falha ao enviar webhook Discord: %s", exc)
        return False


def notificar_discord_alerta(
    titulo: str,
    detalhes: str,
    ip: str = "",
    operadora: str = "Claro S.A.",
    webhook_url: Optional[str] = None,
) -> bool:
    """Envia alerta vermelho no Discord quando houver falha de rede ou bloqueio."""
    url = webhook_url or DEFAULT_DISCORD_WEBHOOK
    if not url:
        return False

    payload = {
        "embeds": [
            {
                "title": f"🚨 [Alerta Usina 4G] {titulo}",
                "description": f"**Atenção:** Ocorreu uma anomalia na esteira de automação móvel.\n\n```{detalhes[:500]}```",
                "color": 0xEF4444,  # Vermelho
                "fields": [
                    {"name": "📱 Aparelho", "value": f"Moto G22 ({operadora})", "inline": True},
                    {"name": "📶 IP Registrado", "value": f"`{ip or 'Desconhecido'}`", "inline": True},
                    {"name": "🔄 Ação Automática", "value": "Modo Avião acionado para rotação", "inline": True},
                ],
                "footer": {
                    "text": f"SixtySix AI 4G Farm • {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                },
            }
        ]
    }

    try:
        r = httpx.post(url, json=payload, timeout=8.0)
        return r.status_code in (200, 204)
    except Exception as exc:
        logger.warning("Falha ao enviar alerta Discord: %s", exc)
        return False


def enviar_heartbeat(
    status: str,
    contas_hoje: int,
    falhas_hoje: int,
    tempo_medio: float,
    ultima_conta: str,
    ip: str,
    operadora: str = "Claro S.A.",
    device: str = "Motorola Moto G22",
    api_url: Optional[str] = None,
    conta: Optional[dict] = None,
) -> Optional[dict]:
    """Envia telemetria da usina para o SixtySix Gateway e captura comandos remotos pendentes."""
    payload = {
        "status": status,
        "device": device,
        "carrier": operadora,
        "network": "4G LTE",
        "ip": ip,
        "contas_hoje": contas_hoje,
        "falhas_hoje": falhas_hoje,
        "tempo_medio": tempo_medio,
        "ultima_conta": ultima_conta,
        "timestamp": datetime.now().isoformat(),
    }

    if conta:
        payload["conta"] = conta
        payload["nova_conta"] = conta
        salvar_conta_local(conta)

    candidate_urls = []
    if api_url:
        candidate_urls.append(api_url.rstrip("/") + "/api/usina-heartbeat")
    else:
        candidate_urls.extend([
            DEFAULT_SIXTYSIX_API.rstrip("/") + "/api/usina-heartbeat",
            "http://127.0.0.1:3000/api/usina-heartbeat",
            "http://127.0.0.1:17866/api/usina-heartbeat",
        ])

    for url in candidate_urls:
        try:
            r = httpx.post(url, json=payload, timeout=4.0)
            if r.status_code == 200:
                res_json = r.json() or {}
                cmd = res_json.get("command")
                if cmd:
                    logger.info("🕹️ [COMANDO REMOTO RECEBIDO] %s", cmd)
                return cmd
        except Exception:
            continue
    return None

