"""Módulo de sincronização e comunicação com o SixtySix Gateway Local.

Permite consultar a próxima matriz de remix e registrar automaticamente
as novas pontes criadas na Lovable direto no pool do SixtySix.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger("qa_framework.gateway_sync")


class SixtySixGatewaySync:
    """Cliente HTTP para comunicação com o SixtySix Local Gateway."""

    def __init__(self, gateway_url: str = "http://127.0.0.1:17866", timeout: float = 10.0) -> None:
        self.gateway_url = gateway_url.rstrip("/")
        self.timeout = timeout

    async def check_gateway_status(self) -> Dict[str, Any]:
        """Verifica a saúde do SixtySix Gateway e o tamanho do pool de pontes."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.gateway_url}/")
                if resp.status_code == 200:
                    return resp.json()
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

    async def get_next_matrix(self) -> Optional[Dict[str, Any]]:
        """Obtém a próxima matriz recomendada para remix pelo Gateway."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(f"{self.gateway_url}/api/public/v1/matrix/next")
                if resp.status_code == 200:
                    return resp.json()
                return None
            except Exception as exc:
                logger.error("Falha ao consultar próxima matriz do Gateway: %s", exc)
                return None

    async def register_worker(self, project_origin: str, workspace_label: str = "") -> Dict[str, Any]:
        """Registra uma nova URL de projeto remixado no SixtySix Gateway.

        Args:
            project_origin: URL base do projeto (ex: 'https://meu-projeto.lovable.app').
            workspace_label: Identificador ou nome do perfil associado (ex: 'Perfil 4').

        Returns:
            Dict retornado pelo Gateway indicando sucesso ou motivo da falha.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                payload = {
                    "project_origin": project_origin.strip(),
                    "workspace_label": workspace_label.strip(),
                }
                resp = await client.post(
                    f"{self.gateway_url}/api/public/v1/workers/register",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(
                        "Ponte '%s' registrada com sucesso no SixtySix Gateway! Worker ID: %s",
                        project_origin,
                        data.get("worker_id"),
                    )
                    return data
                return {"registered": False, "error": f"HTTP {resp.status_code}: {resp.text}"}
            except Exception as exc:
                logger.error("Falha ao registrar trabalhador no SixtySix Gateway: %s", exc)
                return {"registered": False, "error": str(exc)}
