"""Cliente de integração assíncrono com a Local API do AdsPower.

Responsável pela comunicação REST com a API local do AdsPower, controle do
ciclo de vida de navegadores (início, parada, verificação de status ativo),
extração do endpoint WebSocket CDP e prevenção estrita de processos órfãos.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set
import httpx

logger = logging.getLogger("qa_framework.adspower")


class AdsPowerError(Exception):
    """Exceção base para erros de integração com AdsPower."""
    pass


class AdsPowerConnectionError(AdsPowerError):
    """Falha de conexão física ou timeout com a API local do AdsPower."""
    pass


class AdsPowerProfileError(AdsPowerError):
    """Erro retornado pela API do AdsPower ao manipular um perfil específico."""
    pass


class AdsPowerClient:
    """Cliente HTTP assíncrono para a AdsPower Local API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:50325",
        api_key: str = "",
        timeout: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key.strip()
        self.timeout = timeout
        self._active_profiles: Set[str] = set()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Inicializa ou reutiliza a sessão HTTP assíncrona."""
        if self._client is None or self._client.is_closed:
            headers = {
                "Accept": "application/json",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
                headers["X-API-KEY"] = self.api_key

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    def _build_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Adiciona api_key aos query params se fornecida."""
        query_params = dict(params or {})
        if self.api_key and "api_key" not in query_params:
            query_params["api_key"] = self.api_key
        return query_params

    def _build_profile_params(self, profile_id: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Constrói parâmetros suportando tanto ID alfanumérico (user_id) quanto número de série (serial_number)."""
        params = dict(extra or {})
        cleaned = str(profile_id).strip()
        if cleaned.isdigit():
            params["serial_number"] = cleaned
        else:
            params["user_id"] = cleaned
        return self._build_params(params)

    async def check_health(self) -> bool:
        """Verifica se a API Local do AdsPower está online e respondendo."""
        client = await self._get_client()
        try:
            resp = await client.get("/status", params=self._build_params())
            if resp.status_code == 200:
                data = resp.json()
                return data.get("code") == 0 or resp.is_success
            return False
        except (httpx.ConnectError, httpx.TimeoutException, Exception) as exc:
            logger.warning("Falha ao comunicar com AdsPower em %s: %s", self.base_url, exc)
            return False

    async def is_profile_active(self, profile_id: str) -> tuple[bool, Optional[str]]:
        """Verifica se o perfil já se encontra com navegador aberto.

        Returns:
            Tupla (is_active, ws_endpoint)
        """
        client = await self._get_client()
        try:
            resp = await client.get(
                "/api/v1/browser/active",
                params=self._build_profile_params(profile_id),
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    status_info = data.get("data", {})
                    status_str = status_info.get("status", "").lower()
                    if status_str == "active":
                        ws = status_info.get("ws", {}).get("puppeteer")
                        return True, ws
            return False, None
        except Exception as exc:
            logger.debug("Não foi possível verificar status ativo de '%s': %s", profile_id, exc)
            return False, None

    async def start_browser(self, profile_id: str) -> str:
        """Inicia o navegador associado ao profile_id e retorna a URL WebSocket CDP.

        Trata perfis já em execução e extrai o endpoint CDP (Playwright/Puppeteer).
        """
        # 1. Verifica se já está aberto para reaproveitar a sessão
        is_active, existing_ws = await self.is_profile_active(profile_id)
        if is_active and existing_ws:
            logger.info("Perfil '%s' já estava aberto. Reutilizando CDP WebSocket.", profile_id)
            self._active_profiles.add(profile_id)
            return existing_ws

        client = await self._get_client()
        try:
            logger.info("Solicitando inicialização do perfil AdsPower '%s'...", profile_id)
            resp = await client.get(
                "/api/v1/browser/start",
                params=self._build_profile_params(profile_id, {"open_tabs": 1}),
            )
        except httpx.ConnectError as exc:
            raise AdsPowerConnectionError(
                f"Impossível conectar ao AdsPower em {self.base_url}. O aplicativo está em execução? Erro: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise AdsPowerConnectionError(
                f"Timeout ao aguardar resposta do AdsPower para o perfil '{profile_id}'."
            ) from exc
        except Exception as exc:
            raise AdsPowerError(f"Erro inesperado de comunicação com AdsPower: {exc}") from exc

        if resp.status_code != 200:
            raise AdsPowerProfileError(
                f"AdsPower retornou HTTP {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        code = data.get("code")
        msg = data.get("msg", "Erro desconhecido")

        if code != 0:
            # Em alguns casos onde o perfil já estava abrindo ou aberto
            if "already open" in msg.lower() or "active" in msg.lower():
                active, ws_endpoint = await self.is_profile_active(profile_id)
                if active and ws_endpoint:
                    self._active_profiles.add(profile_id)
                    return ws_endpoint

            raise AdsPowerProfileError(
                f"Falha na inicialização do perfil AdsPower '{profile_id}'. Código: {code}, Mensagem: {msg}"
            )

        ws_data = data.get("data", {}).get("ws", {})
        ws_endpoint = ws_data.get("puppeteer")

        if not ws_endpoint:
            # Fallback para debug_port se ws não vier formatado
            debug_port = data.get("data", {}).get("debug_port")
            if debug_port:
                ws_endpoint = f"http://127.0.0.1:{debug_port}"
            else:
                raise AdsPowerProfileError(
                    f"AdsPower não retornou endpoint WebSocket CDP para o perfil '{profile_id}'."
                )

        self._active_profiles.add(profile_id)
        logger.info("Perfil AdsPower '%s' iniciado com sucesso. CDP: %s", profile_id, ws_endpoint)
        return ws_endpoint

    async def stop_browser(self, profile_id: str) -> bool:
        """Encerra com segurança o navegador associado ao profile_id."""
        client = await self._get_client()
        try:
            logger.info("Encerrando navegador do perfil AdsPower '%s'...", profile_id)
            resp = await client.get(
                "/api/v1/browser/stop",
                params=self._build_profile_params(profile_id),
            )
            self._active_profiles.discard(profile_id)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    logger.info("Perfil AdsPower '%s' finalizado com sucesso.", profile_id)
                    return True
                logger.warning(
                    "AdsPower respondeu com código %s ao fechar perfil '%s': %s",
                    data.get("code"),
                    profile_id,
                    data.get("msg"),
                )
            return False
        except Exception as exc:
            self._active_profiles.discard(profile_id)
            logger.warning("Falha ao solicitar fechamento do perfil '%s': %s", profile_id, exc)
            return False

    async def close_all_active(self) -> None:
        """Garante o fechamento de todos os perfis abertos para evitar processos órfãos."""
        if not self._active_profiles:
            return

        logger.info("Encerrando %d perfis AdsPower ativos remanescentes...", len(self._active_profiles))
        for profile_id in list(self._active_profiles):
            await self.stop_browser(profile_id)
        self._active_profiles.clear()

    async def aclose(self) -> None:
        """Fecha o cliente HTTP e todos os perfis gerenciados."""
        await self.close_all_active()
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> AdsPowerClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.aclose()

