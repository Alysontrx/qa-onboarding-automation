"""Gerenciador de sessões de navegador Playwright.

Suporta conexão via CDP (Chrome DevTools Protocol) para perfis gerenciados pelo
AdsPower, bem como execução isolada em Chromium local para desenvolvimento e testes
unitários/CI, garantindo liberação completa de recursos e encerramento limpo.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, Set
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from config.settings import Settings, get_settings
from core.adspower import AdsPowerClient, AdsPowerError

logger = logging.getLogger("qa_framework.browser_manager")


@dataclass(eq=False)
class BrowserSession:
    """Representa uma sessão ativa de navegador Playwright."""

    profile_id: str
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page
    is_adspower: bool
    adspower_client: Optional[AdsPowerClient] = None

    async def close(self) -> None:
        """Encerra com segurança a página, contexto, browser e processo associado."""
        # 1. Fecha a página
        try:
            if not self.page.is_closed():
                await self.page.close()
        except Exception as exc:
            logger.debug("Erro ao fechar página do perfil '%s': %s", self.profile_id, exc)

        # 2. Fecha o contexto
        try:
            await self.context.close()
        except Exception as exc:
            logger.debug("Erro ao fechar contexto do perfil '%s': %s", self.profile_id, exc)

        # 3. Desconecta ou fecha o navegador
        try:
            if self.is_adspower:
                await self.browser.close()
            else:
                await self.browser.close()
        except Exception as exc:
            logger.debug("Erro ao desconectar browser do perfil '%s': %s", self.profile_id, exc)

        # 4. Encerra o processo no AdsPower se aplicável
        if self.is_adspower and self.adspower_client:
            try:
                await self.adspower_client.stop_browser(self.profile_id)
            except Exception as exc:
                logger.warning("Falha ao parar perfil AdsPower '%s': %s", self.profile_id, exc)


class BrowserManager:
    """Gerenciador do ciclo de vida das sessões do navegador."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        adspower_client: Optional[AdsPowerClient] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._adspower_client = adspower_client
        self._active_sessions: Set[BrowserSession] = set()
        self._playwright: Optional[Playwright] = None

    async def _ensure_playwright(self) -> Playwright:
        """Inicializa a instância principal do Playwright sob demanda."""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        return self._playwright

    def get_adspower_client(self) -> AdsPowerClient:
        """Obtém ou instancia o cliente AdsPower."""
        if self._adspower_client is None:
            self._adspower_client = AdsPowerClient(
                base_url=self.settings.adspower_url,
                api_key=self.settings.adspower_api_key,
                timeout=float(self.settings.default_timeout) / 1000.0 * 2,
            )
        return self._adspower_client

    async def open_session(self, profile_id: str) -> BrowserSession:
        """Abre uma nova sessão para o perfil especificado.

        No modo AdsPower:
            Inicia o perfil via Local API, obtém o WebSocket CDP e conecta.
        No modo Local:
            Inicia uma instância limpa de Chromium do Playwright.
        """
        playwright = await self._ensure_playwright()

        if self.settings.use_adspower:
            adspower = self.get_adspower_client()
            ws_endpoint = await adspower.start_browser(profile_id)

            try:
                logger.info("Conectando Playwright ao WebSocket CDP: %s", ws_endpoint)
                browser = None
                for cdp_attempt in range(1, 4):
                    try:
                        browser = await playwright.chromium.connect_over_cdp(
                            ws_endpoint,
                            timeout=self.settings.default_timeout,
                        )
                        break
                    except Exception as cdp_err:
                        if cdp_attempt < 3:
                            logger.warning(
                                "Aguardando porta CDP do AdsPower (%s) responder (tentativa %d/3)...",
                                profile_id,
                                cdp_attempt,
                            )
                            await asyncio.sleep(1.0)
                        else:
                            raise cdp_err

                # AdsPower já possui um contexto e aba principal
                contexts = browser.contexts
                if contexts:
                    context = contexts[0]
                else:
                    context = await browser.new_context()

                pages = context.pages
                page = pages[0] if pages else await context.new_page()

                # Desativa emulação de celular e limitações de rede (Fast 4G) herdadas do perfil AdsPower
                try:
                    cdp = await context.new_cdp_session(page)
                    await cdp.send("Network.emulateNetworkConditions", {
                        "offline": False,
                        "latency": 0,
                        "downloadThroughput": -1,
                        "uploadThroughput": -1,
                    })
                    await cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": False})
                    await cdp.send("Emulation.setDeviceMetricsOverride", {
                        "width": 1280,
                        "height": 900,
                        "deviceScaleFactor": 1,
                        "mobile": False,
                    })
                    logger.info("[%s] Resolução ajustada para Desktop (1280x900) e throttling de rede desligado.", profile_id)
                except Exception as cdp_over_err:
                    logger.debug("[%s] Não foi possível aplicar overrides de mobile via CDP: %s", profile_id, cdp_over_err)

                try:
                    await page.set_viewport_size({"width": 1280, "height": 900})
                except Exception:
                    pass

                session = BrowserSession(
                    profile_id=profile_id,
                    playwright=playwright,
                    browser=browser,
                    context=context,
                    page=page,
                    is_adspower=True,
                    adspower_client=adspower,
                )
                self._active_sessions.add(session)
                return session

            except Exception as exc:
                logger.error(
                    "Falha ao conectar CDP para o perfil '%s'. Encerrando processo no AdsPower.",
                    profile_id,
                )
                await adspower.stop_browser(profile_id)
                raise AdsPowerError(f"Falha ao conectar CDP Playwright: {exc}") from exc

        else:
            # Modo Local (Playwright Standalone)
            logger.info("Iniciando Chromium local para o perfil '%s'...", profile_id)
            browser = await playwright.chromium.launch(
                headless=self.settings.headless,
                timeout=self.settings.default_timeout,
            )
            context = await browser.new_context()
            page = await context.new_page()

            session = BrowserSession(
                profile_id=profile_id,
                playwright=playwright,
                browser=browser,
                context=context,
                page=page,
                is_adspower=False,
                adspower_client=None,
            )
            self._active_sessions.add(session)
            return session

    async def close_session(self, session: BrowserSession) -> None:
        """Encerra e desvincula a sessão ativa."""
        try:
            await session.close()
        finally:
            self._active_sessions.discard(session)

    async def close_all(self) -> None:
        """Encerra todas as sessões ativas e desliga o Playwright."""
        sessions = list(self._active_sessions)
        for session in sessions:
            await self.close_session(session)

        if self._adspower_client:
            await self._adspower_client.aclose()

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as exc:
                logger.debug("Erro ao parar Playwright: %s", exc)
            self._playwright = None
