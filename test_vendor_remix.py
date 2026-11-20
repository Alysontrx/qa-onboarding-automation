"""Executa o metodo oficial do fornecedor (API Remix + Castle) adaptado para nossa operacao SixtySix.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import sys
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vendor_remix")

CASTLE_PK = "pk_TaKsqF94pjCsoyepV6mH3V24AXoM6A7M"
SIX_GATEWAY_URL = "http://127.0.0.1:17866"
DEFAULT_MATRIX_ID = "b9408f43-30ad-4673-a65c-a5e2f1be699b"

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
    logger.info("[GATEWAY SIXTYSIX] Testando resposta do Claude Opus na porta 17866...")
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
                "content": "Ola Claude! Responda em uma frase confirmando que voce e o Claude Opus e que o gateway SixtySix esta funcionando.",
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
                logger.info("[SUCESSO TOTAL] Resposta recebida:")
                print(f"\n🤖 CLAUDE OPUS RESPONDEU:\n\"{text.strip()}\"\n")
                return True
            else:
                logger.warning("[GATEWAY] Status HTTP %d: %s", resp.status_code, resp.text[:250])
                return False
    except Exception as exc:
        logger.error("[GATEWAY] Erro ao conectar ao Gateway: %s", exc)
        return False


async def run():
    email = "alisson.mendes01@sixtysix.online"
    password = "SixTest@2026!Dev"
    matrix_id = "448b5334-3b25-4ed6-9e4d-b6ce9035dd07"

    logger.info("[INICIO] Executando metodo oficial do fornecedor para: %s", email)

    async with async_playwright() as p:
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

        # 1. Abre a página inicial / login
        logger.info("[ETAPA 1] Acessando Lovable...")
        await page.goto("https://lovable.dev/projects", wait_until="domcontentloaded")
        await asyncio.sleep(2.0)

        # Se precisar de login
        if "login" in page.url.lower():
            logger.info("[LOGIN] Preenchendo credenciais na pagina...")
            try:
                # Banner de cookies
                await page.evaluate("""() => {
                    const b = Array.from(document.querySelectorAll('button')).find(el => (el.innerText || '').includes('Aceitar todos'));
                    if (b) b.click();
                }""")
            except Exception:
                pass

            email_inp = await page.wait_for_selector("input[type='email'], input[name='email']", timeout=8000)
            if email_inp:
                await email_inp.fill(email)
                await page.press("input[type='email']", "Enter")
                await asyncio.sleep(2.0)

            pwd_inp = await page.wait_for_selector("input[type='password']", timeout=8000)
            if pwd_inp:
                await pwd_inp.fill(password)
                await asyncio.sleep(0.5)
                entrar_btn = await page.query_selector("button:has-text('Entrar'), button:has-text('Log in'), button[type='submit']")
                if entrar_btn:
                    try:
                        await entrar_btn.click(timeout=3000)
                    except Exception:
                        await page.press("input[type='password']", "Enter")
                else:
                    await page.press("input[type='password']", "Enter")

                try:
                    await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=15000)
                except Exception:
                    pass
                logger.info("[LOGIN] Autenticacao realizada! URL atual: %s", page.url)
                await asyncio.sleep(3.0)

        # 2. Extrai tokens da sessao (Firebase Auth do IndexedDB ou localStorage + Castle Token)
        logger.info("[ETAPA 2] Extraindo Firebase Auth JWT e Token Castle via browser...")
        session_data = await page.evaluate(f"""async () => {{
            let jwt = '';
            let uid = '';

            // 1. Tenta localStorage
            for (let i = 0; i < localStorage.length; i++) {{
                const k = localStorage.key(i);
                if (k && k.includes('firebase')) {{
                    try {{
                        const v = JSON.parse(localStorage.getItem(k));
                        if (v && v.stsTokenManager?.accessToken) {{
                            jwt = v.stsTokenManager.accessToken;
                            uid = v.uid || '';
                        }}
                    }} catch (e) {{}}
                }}
            }}

            // 2. Se nao achou no localStorage, le do IndexedDB (padrao do Firebase Web SDK)
            if (!jwt) {{
                try {{
                    const dbReq = indexedDB.open('firebaseLocalStorageDb');
                    const db = await new Promise((res, rej) => {{
                        dbReq.onsuccess = () => res(dbReq.result);
                        dbReq.onerror = () => rej(dbReq.error);
                    }});
                    const tx = db.transaction(['firebaseLocalStorage'], 'readonly');
                    const store = tx.objectStore('firebaseLocalStorage');
                    const allReq = store.getAll();
                    const records = await new Promise((res, rej) => {{
                        allReq.onsuccess = () => res(allReq.result);
                        allReq.onerror = () => rej(allReq.error);
                    }});
                    if (records && records.length > 0) {{
                        for (const r of records) {{
                            const v = r.value || r;
                            if (v && v.stsTokenManager?.accessToken) {{
                                jwt = v.stsTokenManager.accessToken;
                                uid = v.uid || '';
                                break;
                            }}
                        }}
                    }}
                }} catch (e) {{}}
            }}

            let castleToken = '';
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
                    castleToken = await inst.createRequestToken();
                }}
            }} catch (e) {{}}

            const lsKeys = Object.keys(localStorage);
            return {{ jwt, uid, castleToken, url: window.location.href, lsKeys }};
        }}""")

        jwt = session_data.get("jwt") or ""
        uid = session_data.get("uid") or ""
        castle_token = session_data.get("castleToken") or ""
        ls_keys = session_data.get("lsKeys") or []
        logger.info("[AUTH] LocalStorage Keys: %s", ls_keys[:10])
        logger.info("[AUTH] JWT obtido: %s... (len=%d) | UID: %s | Castle Token: %s...", 
                    jwt[:20] if jwt else "NENHUM", len(jwt), uid, castle_token[:15] if castle_token else "NENHUM")

        if not jwt:
            logger.error("[ERRO FATAL] Sessao nao encontrada em localStorage. Aguardando 10s para inspecionar...")
            await asyncio.sleep(10.0)
            await browser.close()
            return

        # 3. Executa Onboarding de API (Método Oficial do Fornecedor)
        logger.info("[ETAPA 3] Executando Onboarding de API (dispensa telas de onboarding)...")
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
            "Origin": "https://lovable.dev",
            "Referer": "https://lovable.dev/",
        }

        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            # 3.1 Display Name
            if uid:
                try:
                    await client.put(f"https://api.lovable.dev/user/{uid}", json={"attributes": {"display_name": "Alysson"}})
                except Exception:
                    pass

            # 3.2 Marketing consent
            try:
                await client.post("https://api.lovable.dev/user/marketing-email-consent", json={
                    "surface": "getting_started",
                    "wording_version": "2026-09-17",
                    "locale": "pt-BR",
                    "marketing_refused": True,
                })
            except Exception:
                pass

            # 3.3 Segmentation
            try:
                await client.post("https://api.lovable.dev/user/segmentation", json={
                    "role": "other",
                    "company_size": "solo",
                })
            except Exception:
                pass

            # 3.4 Busca o Workspace ID
            logger.info("[ETAPA 4] Buscando Workspace ID da conta...")
            ws_id = None
            for _ in range(15):
                resp_ws = await client.get("https://api.lovable.dev/user/workspaces")
                if resp_ws.status_code == 200:
                    data_ws = resp_ws.json()
                    workspaces = data_ws.get("workspaces", [])
                    if workspaces and workspaces[0].get("id"):
                        ws_id = str(workspaces[0]["id"])
                        break
                await asyncio.sleep(0.5)

            if not ws_id:
                logger.error("[ERRO FATAL] Nenhum workspace retornado pela API da Lovable.")
                await browser.close()
                return

            logger.info("[WORKSPACE] Workspace ID ativo: %s", ws_id)

            # 4. Dispara o Remix via API oficial (Zero dependência de cliques na tela)
            logger.info("[ETAPA 5] Disparando Remix via API Oficial da Lovable...")
            candidate_matrices = [
                "448b5334-3b25-4ed6-9e4d-b6ce9035dd07",
                "8e6c48d8-2e72-4d3f-afa0-0a070e85c2f5",
                matrix_id,
            ]
            chosen_matrix = None
            job_id = None

            for m_id in candidate_matrices:
                logger.info("[TESTE MATRIZ] Testando matriz: %s...", m_id)
                try:
                    r_pref = await client.post(f"https://api.lovable.dev/projects/{m_id}/remix/preflight", json={"workspace_id": ws_id})
                    logger.info("[PREFLIGHT] Matriz %s -> Status %d", m_id, r_pref.status_code)
                except Exception as e:
                    logger.warning("[PREFLIGHT] Aviso: %s", e)

                project_name = f"SixtySix Bridge {secrets.randbelow(8000) + 1000}"
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

                r_init = await client.post(f"https://api.lovable.dev/projects/{m_id}/remix/init", json=init_payload)
                logger.info("[REMIX INIT] Matriz %s -> Status %d: %s", m_id, r_init.status_code, r_init.text[:150])

                if r_init.status_code in (200, 201):
                    job_id = (r_init.json() or {}).get("job_id")
                    if job_id:
                        chosen_matrix = m_id
                        logger.info("🎉 [MATRIZ VALIDA] Iniciado com sucesso na matriz: %s (job_id: %s)", chosen_matrix, job_id)
                        break

            if not chosen_matrix or not job_id:
                logger.error("[FALHA] Nenhuma matriz de remix respondeu com sucesso.")
                await browser.close()
                return

            matrix_id = chosen_matrix

            logger.info("[JOB REMIX] Job ID iniciado: %s. Acompanhando progresso em tempo real...", job_id)

            # 5. Polling de Progresso (Método Oficial do Fornecedor)
            t_start = time.time()
            new_project_url = None
            last_step = ""

            while time.time() - t_start < 180:
                r_prog = await client.get(
                    f"https://api.lovable.dev/projects/{matrix_id}/remix/progress",
                    params={"job_id": job_id},
                )
                if r_prog.status_code == 200:
                    prog = r_prog.json() or {}
                    status = str(prog.get("status") or "").lower()
                    step_raw = str(prog.get("step") or "").lower()
                    step_desc = REMIX_STEP_LABELS.get(step_raw, step_raw or status)

                    if step_desc != last_step:
                        last_step = step_desc
                        logger.info("  ⏳ [PROCESSO REMIX] %s (tempo: %.1fs)", step_desc, time.time() - t_start)

                    if status in ("error", "failed"):
                        logger.error("[ERRO REMIX] Lovable falhou ao processar o remix: %s", prog)
                        break

                    # Verifica se o projeto foi concluído
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
                        if pid and re.fullmatch(r"[A-Za-z0-9_-]+", pid) and pid != matrix_id:
                            new_project_url = f"https://lovable.dev/projects/{pid}"
                            break

                    if status == "completed" and new_project_url:
                        logger.info("[SUCESSO REMIX] Projeto concluido! URL: %s", new_project_url)
                        break

                await asyncio.sleep(1.0)

            if not new_project_url:
                logger.error("[ERRO] Timeout aguardando conclusao do remix.")
                await browser.close()
                return

            # 6. Acorda o container e registra no SixtySix Gateway
            new_pid = re.search(r"/projects/([a-zA-Z0-9_-]+)", new_project_url).group(1)
            logger.info("[CONTAINER] Acordando o novo projeto: %s...", new_pid)
            try:
                await client.get(f"https://api.lovable.dev/projects/{new_pid}/details?include_user_details=true")
                await client.post(f"https://api.lovable.dev/projects/{new_pid}/presence")
            except Exception:
                pass

            # Navega o navegador para o novo projeto no editor
            logger.info("[NAVEGADOR] Abrindo o editor do novo projeto (%s)...", new_pid)
            await page.goto(new_project_url, wait_until="domcontentloaded")
            await asyncio.sleep(6.0)

            # Procura e clica no botão "Publish" / "Publicar" se disponível
            logger.info("[PUBLICACAO] Verificando botao de Publicacao no editor...")
            try:
                publish_btn = await page.wait_for_selector(
                    "button:has-text('Publish'), button:has-text('Publicar'), button:has-text('Share'), button:has-text('Compartilhar')",
                    timeout=8000,
                    state="visible",
                )
                if publish_btn:
                    btn_t = (await publish_btn.inner_text()).strip()
                    logger.info("[PUBLICACAO] Botao encontrado: '%s'. Clicando...", btn_t)
                    await publish_btn.click()
                    await asyncio.sleep(2.0)

                    # Se abriu dropdown/modal de publicacao com botao confirmar
                    confirm_btn = await page.query_selector("button:has-text('Publish to'), button:has-text('Publish updates'), button:has-text('Publicar'), button[type='submit']")
                    if confirm_btn and await confirm_btn.is_visible():
                        logger.info("[PUBLICACAO] Confirmando publicacao...")
                        await confirm_btn.click()
                        await asyncio.sleep(4.0)
            except Exception as e:
                logger.warning("[PUBLICACAO] Aviso na publicacao: %s", e)

            # Localiza link .lovable.app
            app_url = None
            for _ in range(15):
                try:
                    links = await page.query_selector_all("a[href*='.lovable.app']")
                    for l in links:
                        h = await l.get_attribute("href")
                        if h and ".lovable.app" in h:
                            app_url = h.strip()
                            break
                    if app_url:
                        break
                    # Tenta ler texto ou iframes
                    iframe_src = await page.evaluate("""() => {
                        const ifr = document.querySelector('iframe[src*=\"lovable.app\"]');
                        return ifr ? ifr.src : null;
                    }""")
                    if iframe_src and ".lovable.app" in iframe_src:
                        app_url = iframe_src.split('?')[0].rstrip('/')
                        break
                except Exception:
                    pass
                await asyncio.sleep(1.0)

            if not app_url:
                # Fallback: se nao achou publicado, o hosted preview padrao do Lovable é:
                app_url = f"https://id-preview--{new_pid}.lovable.app"
                logger.info("[PREVIEW HOSTED] Usando preview hospedada padrao: %s", app_url)

            logger.info("[DOMINIO PUBLICO] URL do App selecionada: %s", app_url)
            
            # Registra no SixtySix Gateway local
            bridge_url = f"{app_url.rstrip('/')}/api/public/six-test/v1"
            try:
                async with httpx.AsyncClient(timeout=10.0) as gclient:
                    r_reg = await gclient.post(
                        f"{SIX_GATEWAY_URL}/api/public/v1/workers/register",
                        json={"project_origin": app_url},
                    )
                    logger.info("[GATEWAY REGISTRO] Resposta: %d %s", r_reg.status_code, r_reg.text)
            except Exception as gerr:
                logger.warning("[GATEWAY REGISTRO] Erro ao registrar no gateway: %s", gerr)

            # Também adiciona a nova ponte diretamente ao topo de bridges.txt do SixtySix Gateway
            bridges_path = Path("C:/Users/Alysson/Documents/ChatGPT/minha virada de chave/sixtysix-site/integrations/lovable-test/bridges.txt")
            if bridges_path.exists():
                old_lines = [l.strip() for l in bridges_path.read_text(encoding="utf-8").splitlines() if l.strip()]
                if bridge_url not in old_lines:
                    new_content = f"{bridge_url}\n" + "\n".join(old_lines) + "\n"
                    bridges_path.write_text(new_content, encoding="utf-8")
                    logger.info("[BRIDGES TXT] Nova ponte inserida no topo de bridges.txt: %s", bridge_url)

            # Abre a URL no proprio navegador para garantir que os cookies de sessao ativem a preview
            logger.info("[ATIVACAO] Carregando a pagina do app no navegador para aquecer o runtime...")
            try:
                await page.goto(app_url, timeout=15000)
                await asyncio.sleep(4.0)
            except Exception:
                pass

            # 7. Testa a chamada do Claude Opus no SixtySix Gateway!
            logger.info("[TESTE FINAL] Validando Claude Opus no SixtySix Gateway...")
            await asyncio.sleep(2.0)
            claude_ok = await testar_claude_gateway()

            if claude_ok:
                logger.info("🎉🎉🎉 OPERACAO 100% CONCLUIDA COM SUCESSO! CLAUDE OPUS RESPONDEU! 🎉🎉🎉")
            else:
                logger.warning("[FINAL] Remix criado com sucesso! Gateway aguardando ativacao da ponte.")

            await asyncio.sleep(5.0)
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
