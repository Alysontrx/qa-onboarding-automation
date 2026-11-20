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


def is_oauth(text: str) -> bool:
    """Verifica se o texto do botão refere-se a provedores OAuth/SSO."""
    t = (text or "").lower()
    return any(p in t for p in ["google", "github", "apple", "microsoft", "sso"])


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


async def dismiss_getting_started_wizard(page: Page, user_name: str = "Alysson") -> bool:
    """Completa automaticamente todas as etapas do wizard /getting-started da Lovable."""
    start_time = time.perf_counter()
    max_wait = 35.0

    while (time.perf_counter() - start_time) < max_wait:
        cur_url = page.url.lower()
        if "getting-started" not in cur_url and "onboarding" not in cur_url:
            logger.info("Wizard de onboarding /getting-started concluído com sucesso! URL atual: %s", page.url)
            return True

        logger.info("Avançando etapa do wizard Lovable (/getting-started)...")

        # 1. Tenta selecionar uma opção padrão (ex: 'Escuro', 'Claro' ou qualquer card de estilo/função)
        try:
            await page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('div, button, span, p'));
                const escuro = els.find(e => (e.innerText || '').trim().toLowerCase() === 'escuro');
                if (escuro) escuro.click();
            }""")
        except Exception:
            pass

        # 2. Se houver campo de texto (ex: nome do time, projeto ou nome pessoal), preenche
        try:
            inputs = await page.query_selector_all("input[type='text'], input:not([type])")
            for inp in inputs:
                if await inp.is_visible():
                    val = (await inp.input_value()).strip()
                    if not val:
                        await inp.fill(user_name or "Alysson")
                        await asyncio.sleep(0.3)
        except Exception:
            pass

        # 3. Tenta clicar nos botões de avançar ou pular
        clicked = False
        try:
            clicked = await page.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                
                // Prioridade 1: Botão de Pular se existir
                const skipBtn = btns.find(b => {
                    if (b.offsetParent === null) return false;
                    const t = (b.innerText || b.textContent || '').trim().toLowerCase();
                    return t === 'pular' || t === 'skip' || t === 'depois' || t === 'mais tarde';
                });
                if (skipBtn && !skipBtn.disabled) {
                    skipBtn.scrollIntoView();
                    skipBtn.click();
                    return true;
                }

                // Prioridade 2: Botão de Avançar / Continuar
                const nextBtn = btns.find(b => {
                    if (b.offsetParent === null) return false;
                    const t = (b.innerText || b.textContent || '').trim().toLowerCase();
                    return t === 'avançar' || t === 'continuar' || t === 'começar' || t === 'próximo' || t === 'next' || t === 'continue';
                });
                if (nextBtn && !nextBtn.disabled) {
                    nextBtn.scrollIntoView();
                    nextBtn.click();
                    return true;
                }

                return false;
            }""")
        except Exception:
            pass

        if not clicked:
            try:
                btn_loc = page.locator("button:has-text('Avançar'), button:has-text('Continuar'), button:has-text('Começar'), button:has-text('Pular')").first
                if await btn_loc.is_visible(timeout=2000):
                    await btn_loc.click(force=True)
                    clicked = True
            except Exception:
                pass

        await asyncio.sleep(1.5)

    return "getting-started" not in page.url.lower()


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
            logger.info(
                "[%s] Senha preenchida. Aguardando verificação do Cloudflare Turnstile e liberação do botão 'Crie sua conta'...",
                user_data.profile_id,
            )

            submit_clicked = False
            start_submit_wait = time.perf_counter()
            max_submit_wait = 60.0  # Tempo para validação do Turnstile ou clique interativo
            alerted_user = False

            while (time.perf_counter() - start_submit_wait) < max_submit_wait:
                # 1. Verifica se a página já avançou automaticamente (ex: /pricing ou /projects)
                cur_url = page.url.lower()
                if any(x in cur_url for x in ["/pricing", "/projects", "/onboarding"]):
                    logger.info("[%s] Página avançou automaticamente para '%s'!", user_data.profile_id, cur_url)
                    submit_clicked = True
                    break

                # 2. Avalia especificamente o botão VISÍVEL 'Crie sua conta' / cadastro
                btn_state = await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button, [role=\"button\"], input[type=\"submit\"]'));
                    
                    // Identifica se Cloudflare Turnstile está na tela
                    const bodyText = (document.body.innerText || '').toLowerCase();
                    const hasCloudflare = !!document.querySelector('iframe[src*=\"turnstile\"], iframe[src*=\"cloudflare\"], .cf-turnstile') ||
                                          bodyText.includes('confirme que é humano') ||
                                          bodyText.includes('provar que não é um robô');
                    const isCloudflareSuccess = bodyText.includes('sucesso!') || bodyText.includes('success!');

                    // Procura o botão específico de cadastro visível
                    const targetBtn = btns.find(b => {
                        if (!b || b.offsetParent === null) return false;
                        const t = (b.textContent || b.value || '').trim().toLowerCase();
                        if (t.includes('google') || t.includes('github') || t.includes('apple') || t.includes('sso') || t.includes('editar')) return false;
                        return t.includes('crie sua conta') || t.includes('criar conta') || t.includes('create your account') || t.includes('finalizar cadastro') || b.getAttribute('data-testid') === 'btn-submit';
                    });

                    if (!targetBtn) {
                        return { found: false, disabled: true, text: '', hasCloudflare, isCloudflareSuccess };
                    }

                    const isDisabled = targetBtn.disabled ||
                                       targetBtn.hasAttribute('disabled') ||
                                       targetBtn.getAttribute('aria-disabled') === 'true' ||
                                       targetBtn.classList.contains('disabled');

                    return {
                        found: true,
                        disabled: isDisabled,
                        text: (targetBtn.textContent || targetBtn.value || '').trim(),
                        hasCloudflare,
                        isCloudflareSuccess
                    };
                }""")

                if btn_state.get("hasCloudflare") and btn_state.get("disabled") and not btn_state.get("isCloudflareSuccess"):
                    if not alerted_user:
                        logger.warning(
                            "[%s] [CLOUDFLARE] Caixinha 'Confirme que é humano' detectada! Por favor clique nela na janela do AdsPower!",
                            user_data.profile_id,
                        )
                        print(
                            f"\n>>> [PERFIL {user_data.profile_id}] Clique na caixinha 'Confirme que é humano' na janela do AdsPower! <<<\n",
                            flush=True,
                        )
                        alerted_user = True

                if btn_state.get("found") and not btn_state.get("disabled"):
                    logger.info(
                        "[%s] Botão de submissão habilitado ('%s'). Clicando para finalizar cadastro...",
                        user_data.profile_id,
                        btn_state.get("text") or "Submit",
                    )
                    await page.evaluate("""() => {
                        const btns = Array.from(document.querySelectorAll('button, [role=\"button\"], input[type=\"submit\"]'));
                        const targetBtn = btns.find(b => {
                            if (!b || b.offsetParent === null) return false;
                            const t = (b.textContent || b.value || '').trim().toLowerCase();
                            if (t.includes('google') || t.includes('github') || t.includes('apple') || t.includes('sso') || t.includes('editar')) return false;
                            return t.includes('crie sua conta') || t.includes('criar conta') || t.includes('create your account') || t.includes('finalizar cadastro') || b.getAttribute('data-testid') === 'btn-submit';
                        });
                        if (targetBtn && !targetBtn.disabled) {
                            targetBtn.scrollIntoView();
                            targetBtn.click();
                            return true;
                        }
                        return false;
                    }""")
                    try:
                        loc = page.locator("button:has-text('Crie sua conta'), button:has-text('Criar conta'), button:has-text('Create your account'), [data-testid='btn-submit']").first
                        if await loc.is_visible():
                            await loc.click(force=True, timeout=2000)
                    except Exception:
                        pass
                    submit_clicked = True
                    break

                err_elem = await page.query_selector(sel.error_message)
                if err_elem and await err_elem.is_visible():
                    err_txt = (await err_elem.inner_text()).strip()
                    if err_txt:
                        logger.warning("[%s] Erro prematuro exibido na página: '%s'", user_data.profile_id, err_txt)
                        break

                await asyncio.sleep(1.0)

            if not submit_clicked:
                logger.warning("[%s] Botão não habilitou após timeout de espera. Tentando envio alternativo...", user_data.profile_id)
                try:
                    await page.click(sel.submit, timeout=3000, force=True)
                except Exception:
                    await page.press(sel.password, "Enter")

        elif success_early_task in done_early and not success_early_task.cancelled() and not success_early_task.exception():
            logger.info("[%s] Lovable avançou diretamente para envio de link mágico sem exigir senha!", user_data.profile_id)

        # Etapa 5: Aguardar confirmação de sucesso, planos (/pricing) ou erro
        current_step = "AWAIT_CONFIRMATION"

        error_detected = None
        already_logged_in = False
        success_detected = False
        start_conf_wait = time.perf_counter()

        while (time.perf_counter() - start_conf_wait) < 20.0:
            cur_url = page.url.lower()

            # 1. Verifica se avançou para a tela de Preços/Planos (/pricing) ou Projetos (/projects)
            if any(x in cur_url for x in ["/pricing", "/projects", "/onboarding"]):
                logger.info("[%s] Redirecionamento detectado para '%s'! Usuário logado com sucesso.", user_data.profile_id, cur_url)
                already_logged_in = True
                success_detected = True
                break

            # 2. Verifica se renderizou a tela de Preços/Planos
            page_text_check = await page.evaluate("""() => {
                const txt = (document.body.innerText || '').toLowerCase();
                return txt.includes('preços') || txt.includes('pricing') || (txt.includes('free') && txt.includes('r$'));
            }""")
            if page_text_check:
                logger.info("[%s] Tela de seleção de plano detectada na página!", user_data.profile_id)
                already_logged_in = True
                success_detected = True
                break

            # 3. Verifica mensagem de erro na interface
            error_elem = await page.query_selector(sel.error_message)
            if error_elem and await error_elem.is_visible():
                error_detected = (await error_elem.inner_text()).strip()
                if error_detected:
                    break

            # 4. Verifica mensagens tradicionais de sucesso
            try:
                success_elem = await page.query_selector(sel.success_message)
                if success_elem and await success_elem.is_visible():
                    success_detected = True
                    break
            except Exception:
                pass

            await asyncio.sleep(1.0)

        if error_detected:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning(
                "[%s] Formulário rejeitado pela aplicação: '%s'",
                user_data.profile_id,
                error_detected,
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
                error_message=f"Aplicação retornou erro: {error_detected}",
                screenshot_path=screenshot,
            )

        # Se caiu na tela de planos (Preços / Free), clica em 'Começar' no plano Free
        if already_logged_in or "pricing" in page.url.lower():
            try:
                logger.info("[%s] Tela de planos detectada. Clicando em 'Começar' no plano Free...", user_data.profile_id)
                clicked_comecar = await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button, a'));
                    const comecarBtn = btns.find(b => {
                        const t = (b.textContent || '').trim().toLowerCase();
                        return t === 'começar' || t === 'get started' || t.includes('começar');
                    });
                    if (comecarBtn) {
                        comecarBtn.scrollIntoView();
                        comecarBtn.click();
                        return true;
                    }
                    return false;
                }""")
                if clicked_comecar:
                    logger.info("[%s] Botão 'Começar' do plano Free acionado com sucesso!", user_data.profile_id)
                    await asyncio.sleep(2.0)
            except Exception as exc:
                logger.debug("[%s] Não foi necessário clicar em Começar: %s", user_data.profile_id, exc)

        elif cfg.verify_email and not ("127.0.0.1" in target_url or "localhost" in target_url):
            # Se não foi para planos nem logou direto, aguarda o e-mail de ativação via IMAP
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
            await asyncio.sleep(3.0)

            # Aguarda e clica em qualquer botão de confirmação ("Continuar", "Ir para Lovable", etc.)
            try:
                btn_loc = page.locator(
                    "a:has-text('Continuar'), button:has-text('Continuar'), "
                    "a:has-text('Continue'), button:has-text('Continue'), "
                    "a:has-text('Lovable'), button:has-text('Lovable'), "
                    "button:has-text('confirm'), a:has-text('confirm')"
                ).first
                if await btn_loc.is_visible(timeout=5000):
                    await btn_loc.click()
                    logger.info("[%s] Botão de redirecionamento pós-ativação clicado!", user_data.profile_id)
                    await asyncio.sleep(3.0)
            except Exception:
                pass

            # Se cair em /getting-started após a ativação, resolve imediatamente
            if "getting-started" in page.url.lower():
                await dismiss_getting_started_wizard(page, user_data.name)

            # Aguarda validação da página de ativação
            current_step = "VERIFY_ACTIVATION"
            try:
                await page.wait_for_selector(sel.activation_success, timeout=timeout)
            except Exception:
                logger.debug("[%s] Seletor de sucesso de ativação não detectado; página carregada com sucesso.", user_data.profile_id)

        elif not success_detected and ("127.0.0.1" in target_url or "localhost" in target_url):
            raise PlaywrightTimeoutError("Nenhuma confirmação de sucesso ou erro foi encontrada após submissão.")

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
                await asyncio.sleep(3.0)

                # Se o Lovable interceptar com o wizard de onboarding (/getting-started)
                if "getting-started" in page.url.lower() or "onboarding" in page.url.lower():
                    logger.info("[%s] [ÁRVORE REMIX] Wizard de configuração inicial (/getting-started) detectado. Avançando etapas...", user_data.profile_id)
                    await dismiss_getting_started_wizard(page, user_data.name)
                    await page.goto(remix_url, wait_until="domcontentloaded", timeout=timeout)
                    await asyncio.sleep(3.0)

                # Se foi redirecionado para login, autentica automaticamente
                if "login" in page.url.lower():
                    logger.info("[%s] [ÁRVORE REMIX] Redirecionado para login. Autenticando conta recém-ativada...", user_data.profile_id)
                    try:
                        await try_dismiss_cookies()
                        email_input = await page.wait_for_selector(sel.email, timeout=8000)
                        if email_input:
                            await email_input.fill(user_data.email)
                            await page.press(sel.email, "Enter")
                            await asyncio.sleep(2.0)
                            pwd_input = await page.wait_for_selector(sel.password, timeout=8000)
                            if pwd_input:
                                await pwd_input.fill(user_data.password)
                                await page.press(sel.password, "Enter")
                                entrar_btn = await page.query_selector("button:has-text('Entrar'), button:has-text('Log in'), button[type='submit']")
                                if entrar_btn:
                                    await entrar_btn.click()
                                await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=15000)
                                logger.info("[%s] [ÁRVORE REMIX] Login concluído com sucesso!", user_data.profile_id)

                                # Se após o login cair no wizard /getting-started
                                if "getting-started" in page.url.lower():
                                    await dismiss_getting_started_wizard(page, user_data.name)
                                    await page.goto(remix_url, wait_until="domcontentloaded", timeout=timeout)
                                    await asyncio.sleep(3.0)
                    except Exception as login_err:
                        logger.warning("[%s] [ÁRVORE REMIX] Falha na autenticação pós-redirect: %s", user_data.profile_id, login_err)

                # Se ainda estiver no wizard /getting-started
                if "getting-started" in page.url.lower():
                    await dismiss_getting_started_wizard(page, user_data.name)
                    await page.goto(remix_url, wait_until="domcontentloaded", timeout=timeout)
                    await asyncio.sleep(3.0)

                # Garante que está na URL de remix
                if "remix" not in page.url.lower():
                    await page.goto(remix_url, wait_until="domcontentloaded", timeout=timeout)
                    await asyncio.sleep(3.0)

                # Loop de tentativa de clique no botão de Remix (suportando a modal "Couldn't remix this project")
                remix_button_selector = (
                    "button:has-text('Remix project'), button:has-text('Remixar projeto'), "
                    "button:has-text('Remix again'), button:has-text('Remixar novamente'), "
                    "button:has-text('Remix'), button:has-text('Remixar'), "
                    "button:has-text('Use template'), button:has-text('Usar modelo'), "
                    "button:has-text('Fork'), button:has-text('Duplicar'), "
                    "button:has-text('Clonar'), [data-testid*='remix'], button[type='submit']"
                )

                for attempt in range(1, 4):
                    # 1. Verifica se apareceu a modal "Couldn't remix this project"
                    modal_text = await page.evaluate("() => (document.body.innerText || '').toLowerCase()")
                    if "couldn't remix" in modal_text or "não foi possível remixar" in modal_text or "wasn't created" in modal_text:
                        logger.warning("[%s] [ÁRVORE REMIX] Modal 'Couldn't remix' detectada. Tentando 'Remix again'...", user_data.profile_id)
                        remix_again_btn = await page.query_selector("button:has-text('Remix again'), button:has-text('Tentar novamente')")
                        if remix_again_btn and await remix_again_btn.is_visible():
                            await remix_again_btn.click()
                            logger.info("[%s] [ÁRVORE REMIX] Botão 'Remix again' clicado com sucesso!", user_data.profile_id)
                            await asyncio.sleep(4.0)
                        else:
                            open_orig = await page.query_selector("button:has-text('Open original project'), button:has-text('Abrir projeto original')")
                            if open_orig and await open_orig.is_visible():
                                await open_orig.click()
                                await asyncio.sleep(4.0)

                    # 2. Tenta localizar e clicar no botão de remix
                    try:
                        remix_btn = await page.wait_for_selector(remix_button_selector, timeout=8000, state="visible")
                        if remix_btn:
                            await remix_btn.click()
                            logger.info("[%s] [ÁRVORE REMIX] Botão de Remix clicado com sucesso!", user_data.profile_id)
                            break
                    except Exception:
                        pass

                    await asyncio.sleep(2.0)

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

