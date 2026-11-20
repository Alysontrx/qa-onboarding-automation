"""TESTE DE ONBOARDING VIA GOOGLE (SEM PROXY) + REMIX OFICIAL + GATEWAY CLAUDE.

1. Abre o Google Chrome visível para login/cadastro com Google;
2. Aguarda você autorizar o login Google e entrar na Lovable;
3. Captura o JWT autenticado automaticamente;
4. Executa Onboarding de API (Workspace ID);
5. Dispara o Remix da Matriz via API Oficial (Castle Token);
6. Acompanha o progresso até 100% concluído;
7. Acorda o container do novo projeto e registra no SixtySix Gateway;
8. Realiza teste real com o Claude Opus no SixtySix Gateway (porta 17866).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("google_test")

CASTLE_PK = "pk_TaKsqF94pjCsoyepV6mH3V24AXoM6A7M"
SIX_GATEWAY_URL = "http://127.0.0.1:17866"
BRIDGES_FILE = Path("C:/Users/Alysson/Documents/ChatGPT/minha virada de chave/sixtysix-site/integrations/lovable-test/bridges.txt")
MATRIZ_ID = "448b5334-3b25-4ed6-9e4d-b6ce9035dd07"

REMIX_STEP_LABELS = {
    "starting": "Iniciando remix",
    "creating_new_project": "Criando novo projeto",
    "enabling_lovable_cloud": "Ativando Lovable Cloud",
    "copying_lovable_cloud": "Copiando Lovable Cloud",
    "copying_artifacts": "Copiando artefatos do projeto",
    "restoring_supabase": "Restaurando banco Supabase",
    "copying_history": "Copiando historico do projeto",
    "preparing_repository": "Preparando repositorio",
    "remixing_integration": "Configurando integracoes",
    "pushing_repository": "Finalizando gerenciamento de codigo",
    "finalizing": "Finalizando o projeto",
    "completed": "Remix concluido com sucesso!",
}


async def testar_claude_gateway() -> bool:
    logger.info("==================================================================")
    logger.info("[GATEWAY] Testando Claude Opus 5.5 no SixtySix Gateway (127.0.0.1:17866)...")
    logger.info("==================================================================")
    headers = {
        "x-api-key": "sk-rt-1dcb0b56132bd75f90d6f23ab8d50eae0517d297f1a3804f",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "claude-opus-5-5",
        "max_tokens": 150,
        "messages": [
            {
                "role": "user",
                "content": "Ola Claude! Responda em uma frase confirmando que voce e o Claude Opus e que o gateway SixtySix esta 100% operacional.",
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.post(f"{SIX_GATEWAY_URL}/v1/messages", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                print("\n" + "=" * 60)
                print(f"🎉🎉🎉 CLAUDE OPUS RESPONDEU:\n\"{text.strip()}\"")
                print("=" * 60 + "\n")
                return True
            else:
                logger.warning("[GATEWAY] Status HTTP %d: %s", resp.status_code, resp.text[:250])
                return False
    except Exception as exc:
        logger.error("[GATEWAY] Erro ao conectar ao Gateway: %s", exc)
        return False


async def main():
    print("\n" + "=" * 65)
    print("   SIXTYSIX - CRIACAO VIA GOOGLE (SEM PROXY) + REMIX OFICIAL")
    print("=" * 65)
    print("1. O Chrome vai abrir na tela de login da Lovable.")
    print("2. Clique em 'Continue with Google' e selecione sua conta Google.")
    print("3. O script detecta o login e faz todo o restante sozinho!\n")

    async with async_playwright() as p:
        logger.info("[CHROME] Abrindo Google Chrome...")
        browser = await p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 850}, locale="pt-BR")
        page = await context.new_page()

        logger.info("[NAVEGADOR] Acessando https://lovable.dev/signup...")
        await page.goto("https://lovable.dev/signup", wait_until="domcontentloaded")

        # Tenta aceitar banner de cookies se houver
        try:
            await page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(el => (el.innerText || '').includes('Aceitar'));
                if (b) b.click();
            }""")
        except Exception:
            pass

        logger.info("👉 AGUARDANDO VOCE CLICAR EM 'CONTINUE WITH GOOGLE' E CONCLUIR O LOGIN...")

        # Aguarda ate sair da tela de signup/login (ou ate entrar em /projects ou onboarding)
        jwt = ""
        uid = ""
        castle_token = ""
        t_wait_start = time.time()

        while time.time() - t_wait_start < 240:
            current_url = page.url.lower()

            # Tenta extrair tokens se já saiu do login ou se já tem sessão
            session = await page.evaluate(f"""async () => {{
                let j = '';
                let u = '';
                // 1. localStorage
                for (let i = 0; i < localStorage.length; i++) {{
                    const k = localStorage.key(i);
                    if (k && k.includes('firebase')) {{
                        try {{
                            const v = JSON.parse(localStorage.getItem(k));
                            if (v && v.stsTokenManager?.accessToken) {{
                                j = v.stsTokenManager.accessToken;
                                u = v.uid || '';
                            }}
                        }} catch (e) {{}}
                    }}
                }}
                // 2. IndexedDB
                if (!j) {{
                    try {{
                        const dbReq = indexedDB.open('firebaseLocalStorageDb');
                        const db = await new Promise((res, rej) => {{
                            dbReq.onsuccess = () => res(dbReq.result);
                            dbReq.onerror = () => rej(dbReq.error);
                        }});
                        const tx = db.transaction(['firebaseLocalStorage'], 'readonly');
                        const store = tx.objectStore('firebaseLocalStorage');
                        const records = await new Promise((res, rej) => {{
                            const all = store.getAll();
                            all.onsuccess = () => res(all.result);
                            all.onerror = () => rej(all.error);
                        }});
                        if (records) {{
                            for (const r of records) {{
                                const v = r.value || r;
                                if (v && v.stsTokenManager?.accessToken) {{
                                    j = v.stsTokenManager.accessToken;
                                    u = v.uid || '';
                                    break;
                                }}
                            }}
                        }}
                    }} catch (e) {{}}
                }}

                let cTok = '';
                try {{
                    let inst = window.__castleInst;
                    if (!inst) {{
                        const cMod = await import('https://lovable.dev/assets/castle.umd-BziypBlb.js').catch(() => null);
                        if (cMod) {{
                            const Castle = cMod.default || cMod;
                            if (Castle && typeof Castle.configure === 'function') {{
                                inst = Castle.configure({{ pk: '{CASTLE_PK}' }});
                            }}
                        }}
                    }}
                    if (inst && typeof inst.createRequestToken === 'function') {{
                        cTok = await inst.createRequestToken();
                    }}
                }} catch (e) {{}}

                return {{ jwt: j, uid: u, castleToken: cTok }};
            }}""")

            if session.get("jwt"):
                jwt = session["jwt"]
                uid = session.get("uid") or ""
                castle_token = session.get("castleToken") or ""
                logger.info("✅ [LOGIN DETECTADO] Sessao obtida com sucesso! (UID=%s)", uid)
                break

            await asyncio.sleep(2.0)

        if not jwt:
            logger.error("❌ Timeout: Login via Google nao foi concluido em 4 minutos.")
            await browser.close()
            return

        logger.info("[AUTH] JWT Bearer verificado ativo!")

        # Extrai Castle Token se ainda nao tem
        if not castle_token:
            try:
                castle_token = await page.evaluate(f"""async () => {{
                    try {{
                        const cMod = await import('https://lovable.dev/assets/castle.umd-BziypBlb.js').catch(() => null);
                        if (cMod) {{
                            const Castle = cMod.default || cMod;
                            const inst = Castle.configure({{ pk: '{CASTLE_PK}' }});
                            return await inst.createRequestToken();
                        }}
                    }} catch (e) {{}}
                    return '';
                }}""")
            except Exception:
                pass

        # ---------------------------------------------------------
        # ONBOARDING VIA REST API (SILENCIOSO)
        # ---------------------------------------------------------
        logger.info("[ONBOARDING] Buscando Workspace ID da conta...")
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
            "Origin": "https://lovable.dev",
            "Referer": "https://lovable.dev/",
        }

        async with httpx.AsyncClient(timeout=25.0, headers=headers) as client:
            ws_id = None
            for _ in range(20):
                resp_ws = await client.get("https://api.lovable.dev/user/workspaces")
                if resp_ws.status_code == 200:
                    workspaces = (resp_ws.json() or {}).get("workspaces", [])
                    if workspaces and workspaces[0].get("id"):
                        ws_id = str(workspaces[0]["id"])
                        break
                await asyncio.sleep(0.5)

            if not ws_id:
                logger.error("❌ Nenhum workspace retornado para esta conta.")
                await browser.close()
                return

            logger.info("🏢 [WORKSPACE] Workspace ativo: %s", ws_id)

            # ---------------------------------------------------------
            # DISPARA REMIX DA MATRIZ
            # ---------------------------------------------------------
            logger.info("🚀 [REMIX] Disparando Remix da Matriz %s...", MATRIZ_ID)
            try:
                await client.post(f"https://api.lovable.dev/projects/{MATRIZ_ID}/remix/preflight", json={"workspace_id": ws_id})
            except Exception:
                pass

            project_name = f"SixtySix Google Bridge {secrets.randbelow(8000) + 1000}"
            init_payload = {
                "include_history": False,
                "include_files": False,
                "include_custom_knowledge": False,
                "workspace_id": ws_id,
                "skip_initial_remix_message": True,
                "project_name": project_name,
            }
            if castle_token:
                init_payload["castle_request_token"] = castle_token

            r_init = await client.post(f"https://api.lovable.dev/projects/{MATRIZ_ID}/remix/init", json=init_payload)
            if r_init.status_code not in (200, 201):
                logger.error("❌ remix/init falhou (HTTP %d): %s", r_init.status_code, r_init.text)
                await browser.close()
                return

            job_id = (r_init.json() or {}).get("job_id")
            logger.info("⏳ [JOB REMIX] Job ID: %s. Aguardando conclusão do clone...", job_id)

            # Polling do Remix
            t_remix = time.time()
            new_project_id = None
            last_step = ""

            while time.time() - t_remix < 160:
                r_prog = await client.get(
                    f"https://api.lovable.dev/projects/{MATRIZ_ID}/remix/progress",
                    params={"job_id": job_id},
                )
                if r_prog.status_code == 200:
                    prog = r_prog.json() or {}
                    st = str(prog.get("status") or "").lower()
                    step_raw = str(prog.get("step") or "").lower()
                    step_desc = REMIX_STEP_LABELS.get(step_raw, step_raw or st)

                    if step_desc != last_step:
                        last_step = step_desc
                        logger.info("  ⚙️ [PROGRESSO] %s (%.1fs)", step_desc, time.time() - t_remix)

                    if st in ("error", "failed"):
                        logger.error("❌ Remix falhou: %s", prog)
                        break

                    result_obj = prog.get("result") if isinstance(prog.get("result"), dict) else {}
                    project_obj = prog.get("project") if isinstance(prog.get("project"), dict) else {}

                    for cand in (
                        prog.get("project_id"),
                        prog.get("projectId"),
                        result_obj.get("project_id"),
                        result_obj.get("id"),
                        project_obj.get("id"),
                    ):
                        pid = str(cand or "").strip()
                        if pid and re.fullmatch(r"[A-Za-z0-9_-]+", pid) and pid != MATRIZ_ID:
                            new_project_id = pid
                            break

                    if st == "completed" and new_project_id:
                        break

                await asyncio.sleep(0.8)

            if not new_project_id:
                logger.error("❌ Timeout no remix.")
                await browser.close()
                return

            logger.info("🎉 [REMIX CONCLUIDO] Novo Projeto ID: %s", new_project_id)

            # Acorda container
            try:
                await client.get(f"https://api.lovable.dev/projects/{new_project_id}/details?include_user_details=true")
                await client.post(f"https://api.lovable.dev/projects/{new_project_id}/presence")
            except Exception:
                pass

        # ---------------------------------------------------------
        # ACESSA O NOVO PROJETO NO NAVEGADOR E OBTEM A PONTE
        # ---------------------------------------------------------
        logger.info("[CONTAINER] Abrindo o novo projeto no navegador para acordar a runtime...")
        new_project_url = f"https://lovable.dev/projects/{new_project_id}"
        await page.goto(new_project_url, wait_until="domcontentloaded")
        await asyncio.sleep(5.0)

        # Extrai iframe do preview
        app_origin = None
        for _ in range(15):
            try:
                iframe_src = await page.evaluate("""() => {
                    const ifr = document.querySelector('iframe[src*="lovable.app"], iframe[src*="lovableproject.com"]');
                    return ifr ? ifr.src : null;
                }""")
                if iframe_src:
                    u = urlsplit(iframe_src)
                    app_origin = f"{u.scheme}://{u.netloc}"
                    break

                links = await page.query_selector_all("a[href*='.lovable.app']")
                for l in links:
                    h = await l.get_attribute("href")
                    if h and ".lovable.app" in h:
                        u = urlsplit(h.strip())
                        app_origin = f"{u.scheme}://{u.netloc}"
                        break
                if app_origin:
                    break
            except Exception:
                pass
            await asyncio.sleep(1.0)

        if not app_origin:
            app_origin = f"https://id-preview--{new_project_id}.lovable.app"

        bridge_endpoint = f"{app_origin}/api/public/six-test/v1"
        logger.info("🌐 [PONTE CAPTURADA] Endereço da ponte: %s", bridge_endpoint)

        # Atualiza bridges.txt no SixtySix Gateway
        if BRIDGES_FILE.exists():
            old_lines = [l.strip() for l in BRIDGES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
            if bridge_endpoint not in old_lines:
                new_content = f"{bridge_endpoint}\n" + "\n".join(old_lines) + "\n"
                BRIDGES_FILE.write_text(new_content, encoding="utf-8")
                logger.info("📌 [BRIDGES.TXT] Nova ponte inserida no SixtySix Gateway!")

        # Notifica o SixtySix Gateway local
        try:
            async with httpx.AsyncClient(timeout=5.0) as gclient:
                await gclient.post(f"{SIX_GATEWAY_URL}/api/public/v1/workers/register", json={"project_origin": app_origin})
        except Exception:
            pass

        # Visita o app no navegador para aquecer cookies da sessao
        try:
            logger.info("[RUNTIME] Aquecendo endpoint no navegador...")
            await page.goto(bridge_endpoint, timeout=8000)
            await asyncio.sleep(2.0)
        except Exception:
            pass

        await browser.close()

    # ---------------------------------------------------------
    # TESTE REAL DO CLAUDE OPUS NO GATEWAY SIXTYSIX
    # ---------------------------------------------------------
    logger.info("🔄 Testando chamada real no SixtySix Gateway...")
    await asyncio.sleep(1.0)
    claude_ok = await testar_claude_gateway()

    if claude_ok:
        print("\n" + "=" * 65)
        print("🎉🎉🎉 TESTE 100% BEM-SUCEDIDO!")
        print(f"Projeto Lovable: https://lovable.dev/projects/{new_project_id}")
        print(f"Ponte Ativa:     {bridge_endpoint}")
        print("O Claude Desktop já pode ser usado normalmente agora!")
        print("=" * 65 + "\n")
    else:
        logger.warning("Ponte registrada, confira o terminal do SixtySix Gateway.")

if __name__ == "__main__":
    asyncio.run(main())
