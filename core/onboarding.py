"""Módulo de automação do formulário de onboarding.

Implementa a função reutilizável execute_onboarding com esperas explícitas,
seletores configuráveis por data-testid, captura de screenshots apenas em falhas,
medição precisa de tempo e classificação estruturada de resultados.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
import logging
from pathlib import Path
import time
import re
from typing import Optional
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError, Page, TimeoutError as PlaywrightTimeoutError

from config.settings import SelectorsConfig, Settings, get_settings
from core.csv_loader import UserData
from core.email_verifier import EmailVerifier
from core.gateway_sync import SixtySixGatewaySync

logger = logging.getLogger("qa_framework.onboarding")


class ExecutionStatus(str, Enum):
    """Classificação dos resultados de execução conforme especificação de QA."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    PROFILE_ERROR = "PROFILE_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"


@dataclass
class ExecutionResult:
    """Resultado detalhado da execução de onboarding para um perfil/usuário."""

    profile_id: str
    email: str
    status: ExecutionStatus
    step: str
    duration_ms: float
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @property
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "profile_id": self.profile_id,
            "email": self.email,
            "status": self.status.value,
            "step": self.step,
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message or "",
            "screenshot_path": self.screenshot_path or "",
        }


async def _capture_failure_screenshot(
    page: Page,
    profile_id: str,
    log_dir: Path,
    label: str,
) -> Optional[str]:
    """Captura screenshot da tela de erro de forma sanitizada."""
    try:
        screenshots_dir = log_dir / "screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{profile_id}_{label}_{timestamp_str}.png"
        filepath = screenshots_dir / filename
        await page.screenshot(path=str(filepath), full_page=False)
        return str(filepath)
    except Exception as exc:
        logger.debug("Não foi possível capturar screenshot de erro para '%s': %s", profile_id, exc)
        return None


async def execute_onboarding(
    page: Page,
    user_data: UserData,
    settings: Optional[Settings] = None,
    selectors: Optional[SelectorsConfig] = None,
    custom_timeout: Optional[int] = None,
) -> ExecutionResult:
    """Executa o fluxo completo de registro de onboarding na página alvo.

    Args:
        page: Instância de Page do Playwright conectada à sessão.
        user_data: Objeto com credenciais e dados do usuário a registrar.
        settings: Instância de configurações gerais.
        selectors: Seletores da UI (preferência por data-testid).
        custom_timeout: Timeout em milissegundos para as operações.

    Returns:
        ExecutionResult com status classificado, métricas de tempo e detalhes.
    """
    cfg = settings or get_settings()
    sel = selectors or cfg.selectors
    timeout = custom_timeout or cfg.default_timeout
    target_url = cfg.onboarding_url

    start_time = time.perf_counter()
    current_step = "INITIALIZE"

    try:
        # Etapa 1: Navegação para a URL alvo de homologação
        current_step = "NAVIGATE"
        logger.info(
            "[%s] Navegando para '%s' (Timeout: %dms)",
            user_data.profile_id,
            target_url,
            timeout,
        )
        await page.goto(target_url, wait_until="domcontentloaded", timeout=timeout)

        # Lida com eventual banner de consentimento de cookies (ex: Lovable)
        async def try_dismiss_cookies():
            try:
                await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const cookieBtn = btns.find(b => {
                        const t = (b.textContent || '').trim().toLowerCase();
                        return t.includes('aceitar todos') || t.includes('accept all') || t.includes('aceitar') || t.includes('rejeitar');
                    });
                    if (cookieBtn) {
                        cookieBtn.click();
                    }
                    document.querySelectorAll('div').forEach(d => {
                        const style = window.getComputedStyle(d);
                        const txt = (d.innerText || '').toLowerCase();
                        if (style.position === 'fixed' && (txt.includes('cookies') || txt.includes('privacidade'))) {
                            d.remove();
                        }
                    });
                }""")
            except Exception:
                pass

        await try_dismiss_cookies()

        # Etapa 2: Localização e validação dos campos do formulário
        current_step = "IDENTIFY_FIELDS"
        await try_dismiss_cookies()
        await page.wait_for_selector(sel.email, timeout=timeout, state="visible")

        # Etapa 3: Preenchimento dos dados do usuário
        current_step = "FILL_EMAIL"
        await page.fill(sel.email, user_data.email, timeout=timeout)
        await asyncio.sleep(0.5)

        # Se o campo de senha ainda não estiver visível (fluxo de 2 etapas como Lovable), avança a primeira etapa
        try:
            pwd_elem = await page.query_selector(sel.password)
            if not pwd_elem or not await pwd_elem.is_visible():
                await try_dismiss_cookies()
                clicked_js = await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const target = btns.find(b => {
                        const t = (b.textContent || '').trim().toLowerCase();
                        if (t.includes('google') || t.includes('github') || t.includes('apple') || t.includes('sso')) return false;
                        return t === 'continuar' || t === 'continue' || t.includes('continuar') || b.type === 'submit';
                    });
                    if (target) {
                        target.scrollIntoView();
                        target.click();
                        return target.textContent.trim();
                    }
                    return null;
                }""")
                if clicked_js:
                    logger.info("[%s] Botão '%s' acionado com sucesso!", user_data.profile_id, clicked_js)
                else:
                    logger.info("[%s] Botão não localizado via JS. Tentando via Playwright...", user_data.profile_id)
                    btn = await page.query_selector("button:text-is('Continuar'), button:text-is('Continue'), button[type='submit']")
                    if btn:
                        await btn.click(force=True)

                # Pressiona Enter no campo de e-mail por garantia
                await page.press(sel.email, "Enter")
                await asyncio.sleep(2.0)
        except Exception as exc:
            logger.debug("[%s] Falha ao avançar etapa de e-mail: %s", user_data.profile_id, exc)

        current_step = "CHECK_PASSWORD_OR_MAGIC_LINK"
        await try_dismiss_cookies()

        # Aguarda: ou aparece o campo de senha, ou a aplicação já manda o link direto (Magic Link)
        pwd_task = asyncio.create_task(page.wait_for_selector(sel.password, timeout=12000, state="visible"))
        success_early_task = asyncio.create_task(page.wait_for_selector(sel.success_message, timeout=12000, state="visible"))
        error_early_task = asyncio.create_task(page.wait_for_selector(sel.error_message, timeout=12000, state="visible"))

        done_early, pending_early = await asyncio.wait(
            [pwd_task, success_early_task, error_early_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending_early:
            t.cancel()

        if pwd_task in done_early and not pwd_task.cancelled() and not pwd_task.exception():
            # A página exigiu senha! Preenche e submete:
            current_step = "FILL_PASSWORD"
            await page.fill(sel.password, user_data.password, timeout=timeout)
            await asyncio.sleep(0.5)

            # Preenchimento de Nome (se existir na página)
            try:
                name_elem = await page.query_selector(sel.name)
                if name_elem and await name_elem.is_visible():
                    current_step = "FILL_NAME"
                    await name_elem.fill(user_data.name, timeout=timeout)
            except Exception:
                pass

            # Confirmação de senha (se existir)
            try:
                confirm_pwd_elem = await page.query_selector(
                    "input[name*='confirm'], input[id*='confirm'], input[data-testid*='confirm'], input[name*='repassword']"
                )
                if confirm_pwd_elem and await confirm_pwd_elem.is_visible():
                    await confirm_pwd_elem.fill(user_data.password)
            except Exception:
                pass

            # Checkbox de termos (se existir)
            try:
                terms_checkbox = await page.query_selector(
                    "input[type='checkbox'][name*='term'], input[type='checkbox'][name*='agree'], input[type='checkbox'][name*='politica'], input[type='checkbox'][required]"
                )
                if terms_checkbox and await terms_checkbox.is_visible() and not await terms_checkbox.is_checked():
                    await terms_checkbox.check()
            except Exception:
                pass

            # Submissão final do formulário
            current_step = "SUBMIT"
            submit_btn = None
            buttons = await page.query_selector_all("button[type='submit'], form button, button")
            for b in buttons:
                try:
                    if not await b.is_visible():
                        continue
                    b_text = (await b.inner_text()).strip()
                    if is_oauth(b_text):
                        continue
                    if any(w in b_text.lower() for w in ["continuar", "create your account", "criar conta", "crie sua conta", "cadastrar", "sign up"]):
                        submit_btn = b
                        break
                except Exception:
                    continue

            if submit_btn:
                await submit_btn.click(timeout=timeout)
            else:
                try:
                    await page.click(sel.submit, timeout=timeout)
                except Exception:
                    await page.press(sel.password, "Enter")

        elif success_early_task in done_early and not success_early_task.cancelled() and not success_early_task.exception():
            logger.info("[%s] Lovable avançou diretamente para envio de link mágico sem exigir senha!", user_data.profile_id)

        # Etapa 5: Aguardar confirmação de sucesso ou mensagem de erro
        current_step = "AWAIT_CONFIRMATION"

        success_task = asyncio.create_task(
            page.wait_for_selector(sel.success_message, timeout=timeout, state="visible")
        )
        error_task = asyncio.create_task(
            page.wait_for_selector(sel.error_message, timeout=timeout, state="visible")
        )

        done, pending = await asyncio.wait(
            [success_task, error_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancela tarefas que ainda estiverem pendentes
        for task in pending:
            task.cancel()

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        if success_task in done and not success_task.cancelled() and not success_task.exception():
            # Se a verificação por e-mail estiver habilitada, aguarda o link de ativação
            if cfg.verify_email and not ("127.0.0.1" in target_url or "localhost" in target_url):
                current_step = "WAIT_ACTIVATION_EMAIL"
                logger.info(
                    "[%s] Formulário submetido. Aguardando e-mail de ativação para '%s'...",
                    user_data.profile_id,
                    user_data.masked_email,
                )
                verifier = EmailVerifier(
                    host=cfg.imap_host,
                    port=cfg.imap_port,
                    user=cfg.imap_user,
                    password=cfg.imap_password,
                )
                activation_url = await verifier.wait_for_activation_link(
                    recipient_email=user_data.email,
                    timeout=cfg.email_wait_timeout,
                    poll_interval=cfg.email_poll_interval,
                )

                if not activation_url:
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    screenshot = await _capture_failure_screenshot(
                        page, user_data.profile_id, cfg.log_dir, "email_timeout"
                    )
                    return ExecutionResult(
                        profile_id=user_data.profile_id,
                        email=user_data.masked_email,
                        status=ExecutionStatus.TIMEOUT,
                        step="WAIT_ACTIVATION_EMAIL",
                        duration_ms=duration_ms,
                        error_message="E-mail de ativação não recebido dentro do tempo limite.",
                        screenshot_path=screenshot,
                    )

                # Navega até o link de ativação capturado
                current_step = "OPEN_ACTIVATION_LINK"
                logger.info(
                    "[%s] Abrindo link de ativação no navegador: %s",
                    user_data.profile_id,
                    activation_url,
                )
                await page.goto(activation_url, wait_until="domcontentloaded", timeout=timeout)

                # Se a página de ativação exigir clique em botão (ex: "Confirmar", "Ativar", "Continuar")
                try:
                    activate_btn = await page.query_selector(
                        "button:has-text('confirm'), button:has-text('ativar'), button:has-text('verify'), a:has-text('confirm'), button:has-text('continuar')"
                    )
                    if activate_btn and await activate_btn.is_visible():
                        await activate_btn.click(timeout=3000)
                        logger.debug("[%s] Botão de confirmação de ativação clicado.", user_data.profile_id)
                except Exception:
                    pass

                # Aguarda validação da página de ativação
                current_step = "VERIFY_ACTIVATION"
                try:
                    await page.wait_for_selector(sel.activation_success, timeout=timeout)
                except Exception:
                    logger.debug("[%s] Seletor de sucesso de ativação não detectado; página carregada com sucesso.", user_data.profile_id)

            # Etapa 6: Automação do Remix da Matriz Lovable (Árvore Auto-Alimentada)
            if cfg.auto_remix and "lovable.dev" in cfg.onboarding_url:
                current_step = "REMIX_MATRIX"
                try:
                    logger.info(
                        "[%s] [ÁRVORE REMIX] Iniciando processo de Remix automático da matriz...",
                        user_data.profile_id,
                    )
                    gateway_sync = SixtySixGatewaySync(gateway_url=cfg.six_gateway_url)
                    matrix_info = await gateway_sync.get_next_matrix()
                    matrix_id = (matrix_info.get("matrix_id") if matrix_info and matrix_info.get("ok") else None) or cfg.default_matrix_id

                    remix_url = f"https://lovable.dev/projects/{matrix_id}/remix"
                    logger.info(
                        "[%s] [ÁRVORE REMIX] Navegando para Matriz Lovable: %s",
                        user_data.profile_id,
                        remix_url,
                    )
                    await page.goto(remix_url, wait_until="domcontentloaded", timeout=timeout)
                    await asyncio.sleep(2.0)

                    # Tenta clicar no botão de Remix na página
                    remix_button_selector = (
                        "button:has-text('Remix project'), button:has-text('Remix'), "
                        "button:has-text('Use template'), button:has-text('Fork'), "
                        "[data-testid*='remix'], button[type='submit']"
                    )
                    try:
                        remix_btn = await page.wait_for_selector(remix_button_selector, timeout=12000, state="visible")
                        if remix_btn:
                            await remix_btn.click()
                            logger.info("[%s] [ÁRVORE REMIX] Botão de Remix clicado com sucesso!", user_data.profile_id)
                    except Exception as exc:
                        logger.warning("[%s] [ÁRVORE REMIX] Botão de remix não encontrado diretamente: %s", user_data.profile_id, exc)

                    # Aguarda redirecionamento para o novo projeto (/projects/<novo_id>)
                    logger.info("[%s] [ÁRVORE REMIX] Aguardando criação do projeto clonado...", user_data.profile_id)
                    new_project_id = None
                    for _ in range(25):
                        cur_url = page.url
                        match = re.search(r"/projects/([a-zA-Z0-9_-]+)", cur_url)
                        if match and match.group(1) != matrix_id and "remix" not in cur_url:
                            new_project_id = match.group(1)
                            break
                        await asyncio.sleep(1.0)

                    if new_project_id:
                        logger.info(
                            "[%s] [ÁRVORE SUCESSO] Projeto clonado com sucesso! Novo ID: %s",
                            user_data.profile_id,
                            new_project_id,
                        )
                        # Auto-alimenta o pool de matrizes com o novo projeto criado
                        added_matrix = await gateway_sync.register_new_matrix(new_project_id)
                        if added_matrix:
                            logger.info(
                                "[%s] [ÁRVORE MATRIX] Novo projeto adicionado ao pool de matrizes: %s",
                                user_data.profile_id,
                                new_project_id,
                            )

                        # Busca pela URL pública do projeto (.lovable.app) na interface
                        app_url = None
                        try:
                            await asyncio.sleep(4.0)
                            links = await page.query_selector_all("a[href*='.lovable.app']")
                            for link_elem in links:
                                href = await link_elem.get_attribute("href")
                                if href and ".lovable.app" in href:
                                    app_url = href.strip()
                                    break

                            if not app_url:
                                iframes = await page.query_selector_all("iframe[src*='.lovable.app']")
                                for iframe in iframes:
                                    src = await iframe.get_attribute("src")
                                    if src and ".lovable.app" in src:
                                        app_url = src.strip()
                                        break
                        except Exception:
                            pass

                        if app_url:
                            logger.info(
                                "[%s] [ÁRVORE GATEWAY] URL do App detectada: %s. Registrando ponte...",
                                user_data.profile_id,
                                app_url,
                            )
                            reg_worker = await gateway_sync.register_worker(
                                project_origin=app_url,
                                workspace_label=f"Perfil {user_data.profile_id} - {user_data.name}",
                            )
                            if reg_worker.get("registered"):
                                logger.info(
                                    "[%s] [ÁRVORE GATEWAY] Ponte ativada e servindo Claude Opus no SixtySix! Worker ID: %s",
                                    user_data.profile_id,
                                    reg_worker.get("worker_id"),
                                )
                        else:
                            logger.info(
                                "[%s] [ÁRVORE SUCESSO] Projeto %s criado. A handshake interna registrará a ponte assim que o Vite compilar.",
                                user_data.profile_id,
                                new_project_id,
                            )
                    else:
                        logger.warning(
                            "[%s] [ÁRVORE AVISO] Timeout aguardando URL do novo projeto após remix. Matriz tentada: %s",
                            user_data.profile_id,
                            matrix_id,
                        )
                except Exception as exc:
                    logger.warning("[%s] [ÁRVORE ERRO] Falha durante etapa de remix: %s", user_data.profile_id, exc)

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info(
                "[%s] Onboarding concluído com SUCESSO em %.2fms",
                user_data.profile_id,
                duration_ms,
            )
            return ExecutionResult(
                profile_id=user_data.profile_id,
                email=user_data.masked_email,
                status=ExecutionStatus.SUCCESS,
                step="COMPLETE",
                duration_ms=duration_ms,
            )

        if error_task in done and not error_task.cancelled() and not error_task.exception():
            # Captura a mensagem de erro renderizada na interface
            error_elem = await page.query_selector(sel.error_message)
            error_text = (await error_elem.inner_text()).strip() if error_elem else "Erro desconhecido na interface"
            logger.warning(
                "[%s] Formulário rejeitado pela aplicação: '%s'",
                user_data.profile_id,
                error_text,
            )
            screenshot = await _capture_failure_screenshot(
                page, user_data.profile_id, cfg.log_dir, "form_rejected"
            )
            return ExecutionResult(
                profile_id=user_data.profile_id,
                email=user_data.masked_email,
                status=ExecutionStatus.FAILED,
                step="FORM_VALIDATION_ERROR",
                duration_ms=duration_ms,
                error_message=f"Aplicação retornou erro: {error_text}",
                screenshot_path=screenshot,
            )

        # Se nenhum seletor foi localizado dentro do timeout
        raise PlaywrightTimeoutError("Nenhuma confirmação de sucesso ou erro foi encontrada após submissão.")

    except PlaywrightTimeoutError as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.error(
            "[%s] Timeout durante a etapa '%s' (%.2fms): %s",
            user_data.profile_id,
            current_step,
            duration_ms,
            exc,
        )
        screenshot = await _capture_failure_screenshot(
            page, user_data.profile_id, cfg.log_dir, f"timeout_{current_step.lower()}"
        )
        return ExecutionResult(
            profile_id=user_data.profile_id,
            email=user_data.masked_email,
            status=ExecutionStatus.TIMEOUT,
            step=current_step,
            duration_ms=duration_ms,
            error_message=f"Timeout na etapa {current_step}: {exc}",
            screenshot_path=screenshot,
        )

    except PlaywrightError as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.error(
            "[%s] Erro Playwright na etapa '%s': %s",
            user_data.profile_id,
            current_step,
            exc,
        )
        screenshot = await _capture_failure_screenshot(
            page, user_data.profile_id, cfg.log_dir, f"error_{current_step.lower()}"
        )
        return ExecutionResult(
            profile_id=user_data.profile_id,
            email=user_data.masked_email,
            status=ExecutionStatus.FAILED,
            step=current_step,
            duration_ms=duration_ms,
            error_message=f"Erro de automação: {exc}",
            screenshot_path=screenshot,
        )

    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.exception(
            "[%s] Falha inesperada durante o onboarding na etapa '%s': %s",
            user_data.profile_id,
            current_step,
            exc,
        )
        screenshot = await _capture_failure_screenshot(
            page, user_data.profile_id, cfg.log_dir, "unexpected_error"
        )
        return ExecutionResult(
            profile_id=user_data.profile_id,
            email=user_data.masked_email,
            status=ExecutionStatus.FAILED,
            step=current_step,
            duration_ms=duration_ms,
            error_message=f"Erro inesperado: {exc}",
            screenshot_path=screenshot,
        )

