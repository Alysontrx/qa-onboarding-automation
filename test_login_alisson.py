import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome", headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 850})
        page = await context.new_page()
        
        print("Navegando para https://lovable.dev/login...")
        await page.goto("https://lovable.dev/login", wait_until="domcontentloaded")
        await asyncio.sleep(2.0)
        
        # Aceita cookies se houver
        try:
            await page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(el => (el.innerText || '').includes('Aceitar'));
                if (b) b.click();
            }""")
        except Exception:
            pass
            
        print("Preenchendo login...")
        email_inp = await page.wait_for_selector("input[type='email'], input[name='email']", timeout=10000)
        await email_inp.fill("alisson.mendes01@sixtysix.online")
        
        # Clica em continuar
        btn = await page.wait_for_selector("button[type='submit']", timeout=8000)
        await btn.click()
        await asyncio.sleep(2.0)
        
        pwd_inp = await page.wait_for_selector("input[type='password'], input[name='password']", timeout=10000)
        await pwd_inp.fill("SixTest@2026!Dev")
        await asyncio.sleep(0.5)
        
        submit_btn = await page.wait_for_selector("button[type='submit']", timeout=8000)
        await submit_btn.click()
        
        print("Aguardando redirecionamento pos-login...")
        for _ in range(30):
            url = page.url
            print("URL atual:", url)
            if "/projects" in url or url == "https://lovable.dev/":
                print("LOGIN COM SUCESSO!")
                break
            await asyncio.sleep(1.0)
            
        print("Navegando para o projeto b35eca3a-6a1d-409e-a0bb-8fbc954e6d8a...")
        await page.goto("https://lovable.dev/projects/b35eca3a-6a1d-409e-a0bb-8fbc954e6d8a", wait_until="domcontentloaded")
        await asyncio.sleep(6.0)
        print("Pagina do projeto carregada. Titulo:", await page.title())
        
        # Tira screenshot para inspecionar
        await page.screenshot(path="logs/projeto_alisson.png")
        print("Screenshot salva em logs/projeto_alisson.png")
        
        # Procura botao de Publish
        publish_btn = await page.query_selector("button:has-text('Publish'), button:has-text('Publicar')")
        if publish_btn:
            print("Botao Publish encontrado! Clicando...")
            await publish_btn.click()
            await asyncio.sleep(3.0)
            await page.screenshot(path="logs/projeto_alisson_publish.png")
        else:
            print("Botao Publish nao encontrado diretamente. Listando botoes:")
            botoes = await page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim()).filter(Boolean);
            }""")
            print("Botoes visiveis:", botoes)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
