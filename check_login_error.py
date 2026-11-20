import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome", headless=True)
        page = await b.new_page()
        await page.goto("https://lovable.dev/login")
        await asyncio.sleep(2.0)
        await page.fill("input[type='email']", "alisson.mendes01@sixtysix.online")
        await page.click("button[type='submit']")
        await asyncio.sleep(2.5)
        
        # O que tem na tela agora?
        print("Botoes antes da senha:", await page.evaluate("() => Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim())"))
        
        await page.fill("input[type='password']", "SixTest@2026!Dev")
        await asyncio.sleep(1.0)
        
        print("Botoes depois da senha:", await page.evaluate("() => Array.from(document.querySelectorAll('button')).map(b => b.innerText.trim())"))
        
        # Tira screenshot
        await page.screenshot(path="logs/tela_login_senha.png")
        print("Screenshot salva em logs/tela_login_senha.png")
        
        # Clica no submit
        btn = await page.wait_for_selector("button[type='submit']", timeout=5000)
        print("Botao submit disabled?", await btn.is_disabled())
        await btn.click()
        await asyncio.sleep(3.0)
        
        await page.screenshot(path="logs/tela_login_resultado.png")
        print("Screenshot final salva em logs/tela_login_resultado.png")
        print("URL final:", page.url)
        print("Texto na tela:", (await page.text_content("body"))[:300])
        
        await b.close()

if __name__ == "__main__":
    asyncio.run(main())
