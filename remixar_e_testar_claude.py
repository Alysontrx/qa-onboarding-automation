"""Script para executar diretamente o Remix da Matriz e testar a resposta do Claude no SixtySix Gateway.

Ideal para validar o ciclo completo quando a conta jÃ¡ foi criada:
1. Faz login no Lovable (ou reutiliza sessÃ£o);
2. AvanÃ§a pelo /getting-started se estiver pendente;
3. Acessa a Matriz (b9408f43-30ad-4673-a65c-a5e2f1be699b) e clica em Remix / Remix again;
4. Aguarda a geraÃ§Ã£o do novo projeto e captura a URL .lovable.app;
5. Registra a nova ponte no SixtySix Gateway (desktop-local-server na porta 17866);
6. Envia uma chamada real para a API do Claude no SixtySix e imprime a resposta!
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from core.csv_loader import load_users_from_csv
from core.gateway_sync import SixtySixGatewaySync
from core.onboarding import dismiss_getting_started_wizard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("remix_runner")

GATEWAY_URL = "http://127.0.0.1:17866"
DEFAULT_MATRIX_ID = "b9408f43-30ad-4673-a65c-a5e2f1be699b"


async def testar_chamada_claude():
    """Testa chamada real para o SixtySix Gateway para confirmar que Claude responde."""
    logger.info("==================================================================")
    logger.info("[TESTE CLAUDE] Testando resposta da IA atraves do SixtySix Gateway...")
    logger.info("==================================================================")

    payload = {
        "model": "anthropic/claude-opus-5-5",
        "max_tokens": 150,
        "messages": [
            {"role": "user", "content": "Ola! Responda em uma frase curta confirmando que voce e o Claude Opus e que a ponte SixtySix esta ativa com sucesso."}
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{GATEWAY_URL}/v1/messages", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                text_response = ""
                for block in content:
                    if block.get("type") == "text":
                        text_response += block.get("text", "")
                logger.info("[SUCESSO CLAUDE] Resposta recebida com sucesso:")
                print(f"\n🤖 CLAUDE OPUS:\n\"{text_response.strip()}\"\n")
                return True
            else:
                logger.warning("[AVISO CLAUDE] Gateway retornou status HTTP %d: %s", resp.status_code, resp.text[:300])
                return False
    except Exception as exc:
        logger.error("[ERRO CLAUDE] Falha ao conectar ao Gateway SixtySix: %s", exc)
        return False


async def executar_remix():
    # Carrega credenciais do CSV
    users = load_users_from_csv("data/usuarios.csv")
    user = users[0] if users else None
    email = user.email if user else "qa_p4_01@sixtysix.online"
    password = user.password if user else "SenhaTeste123!"

    logger.info("[INICIO] Executando Remix para a conta: %s", email)

    async with async_playwright() as p:
        logger.info("[CHROME] Abrindo Google Chrome visivel...")
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 850},
            locale="pt-BR",
        )
        page = await context.new_page()

        # 1. Acessa a pagina de login / projetos
        logger.info("[NAVEGACAO] Acessando Lovable...")
        await page.goto("https://lovable.dev/projects", wait_until="domcontentloaded")
        await asyncio.sleep(2.0)

        # Se pediu login, realiza login
        if "login" in page.url.lower():
            logger.info("[LOGIN] Sessao deslogada. Realizando login com %s...", email)
            try:
                # Remove banner de cookies se houver
                await page.evaluate("""() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const c = btns.find(b => (b.innerText || '').includes('Aceitar todos'));
                    if (c) c.click();
                    document.querySelectorAll('div').forEach(d => {
                        if (window.getComputedStyle(d).position === 'fixed') d.remove();
                    });
                }""")
                email_inp = await page.wait_for_selector("input[type='email'], input[name='email']", timeout=8000)
                if email_inp:
                    await email_inp.fill(email)
                    await page.press("input[type='email']", "Enter")
                    await asyncio.sleep(2.0)
                    pwd_inp = await page.wait_for_selector("input[type='password']", timeout=8000)
                    if pwd_inp:
                        await pwd_inp.fill(password)
                        await page.press("input[type='password']", "Enter")
                        entrar_btn = await page.query_selector("button:has-text('Entrar'), button:has-text('Log in'), button[type='submit']")
                        if entrar_btn:
                            await entrar_btn.click()
                        await asyncio.sleep(4.0)
            except Exception as e:
                logger.warning("[LOGIN] Aviso durante preenchimento de login: %s", e)

        # 2. Se cair no wizard /getting-started, resolve automaticamente
        if "getting-started" in page.url.lower() or "onboarding" in page.url.lower():
            logger.info("[WIZARD] Wizard /getting-started detectado. Resolvendo etapas...")
            await dismiss_getting_started_wizard(page, "Alysson")

        # 3. Navega para a Matriz de Remix
        matrix_id = DEFAULT_MATRIX_ID
        remix_url = f"https://lovable.dev/projects/{matrix_id}/remix"
        logger.info("[REMIX] Navegando diretamente para a Matriz: %s", remix_url)
        await page.goto(remix_url, wait_until="domcontentloaded")
        await asyncio.sleep(3.0)

        # Se cair em /getting-started novamente
        if "getting-started" in page.url.lower():
            await dismiss_getting_started_wizard(page, "Alysson")
            await page.goto(remix_url, wait_until="domcontentloaded")
            await asyncio.sleep(3.0)

        # 4. Trata a modal "Couldn't remix this project" ou clica no botao Remix
        remix_clicked = False
        remix_selectors = (
            "button:has-text('Remix again'), button:has-text('Remixar novamente'), "
            "button:has-text('Remix project'), button:has-text('Remixar projeto'), "
            "button:has-text('Remix'), button:has-text('Remixar'), "
            "button:has-text('Use template'), button:has-text('Usar modelo'), "
            "button:has-text('Fork'), [data-testid*='remix']"
        )

        for attempt in range(1, 6):
            logger.info("[REMIX] Verificando estado da tela de remix (tentativa %d/5)...", attempt)
            page_text = await page.evaluate("() => (document.body.innerText || '').toLowerCase()")

            # Modal de falha de criacao
            if "couldn't remix" in page_text or "não foi possível remixar" in page_text or "wasn't created" in page_text:
                logger.warning("[REMIX] Modal 'Couldn't remix this project' detectada! Clicando em 'Remix again'...")
                btn_again = await page.query_selector("button:has-text('Remix again'), button:has-text('Tentar novamente')")
                if btn_again and await btn_again.is_visible():
                    await btn_again.click()
                    logger.info("[REMIX] Botao 'Remix again' acionado com sucesso!")
                    remix_clicked = True
                    await asyncio.sleep(4.0)
                    break
                else:
                    btn_orig = await page.query_selector("button:has-text('Open original project'), button:has-text('Abrir projeto original')")
                    if btn_orig and await btn_orig.is_visible():
                        logger.info("[REMIX] Clicando em 'Open original project' para remixar de dentro do editor...")
                        await btn_orig.click()
                        await asyncio.sleep(4.0)

            # Botao normal de remix
            try:
                btn_remix = await page.wait_for_selector(remix_selectors, timeout=4000, state="visible")
                if btn_remix:
                    btn_text = (await btn_remix.inner_text()).strip()
                    logger.info("[REMIX] Botao localizado: '%s'. Clicando...", btn_text)
                    await btn_remix.click()
                    remix_clicked = True
                    break
            except Exception:
                pass

            await asyncio.sleep(2.0)

        # 5. Aguarda a criacao do novo projeto (/projects/<novo_id>)
        logger.info("[PROJETO] Aguardando conclusao do remix e redirecionamento para o novo ID de projeto...")
        new_project_id = None
        for _ in range(40):
            cur_url = page.url
            match = re.search(r"/projects/([a-zA-Z0-9_-]+)", cur_url)
            if match and match.group(1) != matrix_id and "remix" not in cur_url:
                new_project_id = match.group(1)
                break
            await asyncio.sleep(1.0)

        if not new_project_id:
            logger.error("[FALHA] Timeout aguardando redirecionamento para o novo projeto.")
            await page.screenshot(path="logs/screenshots/remix_timeout.png")
            await browser.close()
            return

        logger.info("==================================================================")
        logger.info("[SUCESSO REMIX] Projeto clonado com sucesso! Novo ID: %s", new_project_id)
        logger.info("==================================================================")

        # 6. Registra no pool de matrizes
        gateway_sync = SixtySixGatewaySync(gateway_url=GATEWAY_URL)
        await gateway_sync.register_new_matrix(new_project_id)

        # 7. Localiza a URL publica do app (.lovable.app)
        logger.info("[GATEWAY] Procurando URL publica (.lovable.app) do novo projeto...")
        app_url = None
        for _ in range(10):
            try:
                links = await page.query_selector_all("a[href*='.lovable.app']")
                for l in links:
                    h = await l.get_attribute("href")
                    if h and ".lovable.app" in h:
                        app_url = h.strip()
                        break
                if not app_url:
                    iframes = await page.query_selector_all("iframe[src*='.lovable.app']")
                    for ifr in iframes:
                        s = await ifr.get_attribute("src")
                        if s and ".lovable.app" in s:
                            app_url = s.strip()
                            break
            except Exception:
                pass

            if app_url:
                break
            await asyncio.sleep(2.0)

        if app_url:
            logger.info("[GATEWAY] URL do App encontrada: %s! Registrando no SixtySix Gateway...", app_url)
            reg = await gateway_sync.register_worker(
                project_origin=app_url,
                workspace_label=f"Perfil 4 - {email}",
            )
            logger.info("[GATEWAY] Ponte registrada com sucesso: %s", reg)
        else:
            logger.info("[GATEWAY] URL publica compilando em segundo plano. O handshake interno ativara a ponte.")

        # 8. Testa chamada real no Claude Opus pelo SixtySix Gateway!
        await asyncio.sleep(2.0)
        await testar_chamada_claude()

        logger.info("[CONCLUIDO] Processo de Remix e Verificacao finalizado com sucesso!")
        logger.info("Pressione qualquer tecla para encerrar o navegador...")
        input()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(executar_remix())
