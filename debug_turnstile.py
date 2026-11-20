import asyncio
import time
from playwright.async_api import async_playwright

async def inspect():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        page = await browser.new_page()
        await page.goto("https://lovable.dev/signup", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        try:
            b = await page.query_selector("button:has-text('Aceitar todos')")
            if b:
                await b.click()
        except Exception:
            pass

        em = await page.wait_for_selector("input[name='email']")
        fresh_email = f"qa_fresh_{int(time.time())}@sixtysix.online"
        print("Testing with fresh email:", fresh_email)
        await em.fill(fresh_email)
        btn = await page.wait_for_selector("button[type='submit']")
        await btn.click()
        await asyncio.sleep(3)

        print("URL after email submit:", page.url)
        inputs = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('input')).map(i => ({
                name: i.name, type: i.type, id: i.id, value: i.value ? i.value.substring(0, 20) : ''
            }));
        }""")
        print("Inputs found:", inputs)

        buttons = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button')).map(b => ({
                text: b.innerText.trim(), type: b.type, disabled: b.disabled
            }));
        }""")
        print("Buttons found:", buttons)

        body = await page.evaluate("() => document.body.innerText")
        print("Body text:\n", body[:400])
        await browser.close()

if __name__ == "__main__":
    asyncio.run(inspect())
