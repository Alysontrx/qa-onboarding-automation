import asyncio
import logging
import re
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("get_bridge")

BRIDGES_FILE = Path("C:/Users/Alysson/Documents/ChatGPT/minha virada de chave/sixtysix-site/integrations/lovable-test/bridges.txt")
SIX_GATEWAY_URL = "http://127.0.0.1:17866"

async def testar_claude():
    headers = {
        "x-api-key": "sk-rt-1dcb0b56132bd75f90d6f23ab8d50eae0517d297f1a3804f",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "claude-opus-5-5",
        "max_tokens": 50,
        "messages": [{"role": "user", "content": "Ola Claude! Responda confirmando que voce e o Claude Opus."}],
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{SIX_GATEWAY_URL}/v1/messages", headers=headers, json=payload)
            logger.info("Teste Claude Gateway: HTTP %d | %s", r.status_code, r.text[:200])
            return r.status_code == 200
    except Exception as e:
        logger.error("Erro no teste do gateway: %s", e)
        return False

async def main():
    email = "felipe.costa02@sixtysix.online"
    password = "SixTest@2026!Dev"
    project_id = "1ce5cdc6-9c19-4039-9ad4-b105c9c863b7"

    async with async_playwright() as p:
        logger.info("Iniciando Chrome...")
        browser = await p.chromium.launch(channel="chrome", headless=False, args=["--start-maximized"])
        context = await browser.new_context(viewport={"width": 1280, "height": 850}, locale="pt-BR")
        page = await context.new_page()

        logger.info("Navegando para https://lovable.dev/login...")
        await page.goto("https://lovable.dev/login", wait_until="domcontentloaded")
        await asyncio.sleep(2.0)

        # Cookies
        try:
            await page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(el => (el.innerText || '').includes('Aceitar'));
                if (b) b.click();
            }""")
        except Exception:
            pass

        # Email
        inp_email = await page.wait_for_selector("input[type='email'], input[name='email']", timeout=10000)
        await inp_email.fill(email)
        await asyncio.sleep(0.5)

        # Continuar / Enter
        await page.press("input[type='email'], input[name='email']", "Enter")
        await asyncio.sleep(2.0)

        # Senha
        inp_pw = await page.wait_for_selector("input[type='password'], input[name='password']", timeout=10000)
        await inp_pw.fill(password)
        await asyncio.sleep(0.5)

        # Turnstile se houver
        logger.info("Verificando se ha Turnstile ou se o botao de entrar esta liberado...")
        for _ in range(60):
            tok = await page.evaluate("""() => {
                const inp = document.querySelector("input[name='cf-turnstile-response']");
                return inp ? inp.value : 'none';
            }""")
            if tok != '':
                break
            await asyncio.sleep(0.5)

        # Entrar
        btn_login = await page.query_selector("button:has-text('Entrar'), button:has-text('Log in'), button[type='submit']")
        if btn_login:
            await btn_login.click()
        else:
            await page.press("input[type='password']", "Enter")

        logger.info("Aguardando login concluir...")
        await asyncio.sleep(5.0)

        # Verifica se apareceu erro na tela
        err = await page.evaluate("""() => {
            const el = Array.from(document.querySelectorAll('*')).find(e => 
                (e.innerText || '').includes('denied') || (e.innerText || '').includes('suspicious')
            );
            return el ? el.innerText.trim() : '';
        }""")
        if err:
            logger.error("Erro detectado na tela de login: %s", err)
            await page.screenshot(path="login_error.png")
            await browser.close()
            return

        logger.info("Login bem-sucedido! URL atual: %s", page.url)

        # Navega para o projeto
        target_url = f"https://lovable.dev/projects/{project_id}"
        logger.info("Navegando para o projeto: %s...", target_url)
        await page.goto(target_url, wait_until="domcontentloaded")
        await asyncio.sleep(6.0)

        # Extrai iframe do preview
        app_origin = None
        for attempt in range(15):
            iframe_src = await page.evaluate("""() => {
                const ifr = document.querySelector('iframe[src*="lovable.app"], iframe[src*="lovableproject.com"]');
                return ifr ? ifr.src : null;
            }""")
            if iframe_src:
                u = urlsplit(iframe_src)
                app_origin = f"{u.scheme}://{u.netloc}"
                logger.info("Preview iframe detectado: %s", app_origin)
                break
            await asyncio.sleep(1.0)

        if not app_origin:
            logger.warning("Iframe nao localizado, tirando screenshot...")
            await page.screenshot(path="project_view.png")
            app_origin = f"https://id-preview--{project_id}.lovable.app"

        bridge_url = f"{app_origin}/api/public/six-test/v1"
        logger.info("Configurando ponte no bridges.txt: %s", bridge_url)

        if BRIDGES_FILE.exists():
            old = [l.strip() for l in BRIDGES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
            if bridge_url not in old:
                new_lines = f"{bridge_url}\n" + "\n".join(old) + "\n"
                BRIDGES_FILE.write_text(new_lines, encoding="utf-8")
                logger.info("Ponte salva no bridges.txt!")

        try:
            async with httpx.AsyncClient(timeout=5.0) as gc:
                await gc.post(f"{SIX_GATEWAY_URL}/api/public/v1/workers/register", json={"project_origin": app_origin})
        except Exception:
            pass

        # Visita app para aquecer
        try:
            await page.goto(app_origin, timeout=10000)
            await asyncio.sleep(2.0)
        except Exception:
            pass

        await browser.close()

    # Testa Claude
    logger.info("Testando Claude no SixtySix Gateway...")
    await testar_claude()

if __name__ == "__main__":
    asyncio.run(main())
