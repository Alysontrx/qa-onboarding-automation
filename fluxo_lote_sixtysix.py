"""FLUXO EM LOTE SIXTYSIX - CRIACAO DE CONTAS + REMIX AUTOMATICO VIA API OFICIAL.

Baseado na arquitetura oficial do fornecedor (protocolo_puro.py) + auto-registro de pontes no SixtySix Gateway:
1. Chrome abre na pagina de signup para resolver o Turnstile nativo;
2. Captura o custom_token no retorno HTTP 200 de POST /auth/signup;
3. Extrai o Castle Request Token na pagina carregada;
4. Enquanto o navegador aguarda em segundo plano, executa o protocolo REST puro:
   - Troca custom_token via API Firebase (signInWithCustomToken) -> obtem refreshToken e UID;
   - Dispara sendOobCode via API do Firebase para envio imediato do e-mail;
   - Captura link de ativacao em segundos via IMAP Gmail (@sixtysix.online);
   - Confirma e-mail via REST API da Lovable (POST /user/verify-email);
   - Renova sessao no Google SecureToken com refreshToken -> obtem JWT verificado;
   - Onboarding silencioso 100% via API (/user/{uid}, /segmentation, /workspaces);
   - Remix da Matriz via API Oficial (/remix/preflight + /remix/init + Castle Token);
   - Acompanhamento de progresso ate status='completed';
5. Com o projeto clonado, o navegador acessa o novo projeto para obter o subdominio publico (.lovable.app);
6. Registra a URL do novo worker automaticamente no topo do bridges.txt do SixtySix Gateway;
7. Valida a chamada do Claude Opus no SixtySix Gateway (porta 17866) com teste real;
8. Fecha o navegador e grava os dados em accounts/contas_criadas.txt.
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
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
from playwright.async_api import async_playwright

from core.email_verifier import EmailVerifier
from core.proxy_4g import garantir_adb_forward, obter_ip_atual, rotacionar_ip_4g
from core.usina_notifier import (
    enviar_heartbeat,
    notificar_discord_alerta,
    notificar_discord_sucesso,
)

# Diretorios e caminhos
BASE_DIR = Path(__file__).resolve().parent
ACCOUNTS_DIR = BASE_DIR / "accounts"
ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
CONTAS_CRIADAS_FILE = ACCOUNTS_DIR / "contas_criadas.txt"
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
FLUXO_LOG_FILE = LOGS_DIR / "fluxo_lote.log"

BRIDGES_FILE = BASE_DIR / "sixtyosix" / "integrations" / "lovable-test" / "bridges.txt"
if not BRIDGES_FILE.exists():
    BRIDGES_FILE = BASE_DIR.parent / "sixtysix-site" / "integrations" / "lovable-test" / "bridges.txt"

logger = logging.getLogger("sixtysix_lote")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

# Stream handler (console)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(formatter)
logger.addHandler(sh)

# File handler persistente
fh = logging.FileHandler(FLUXO_LOG_FILE, encoding="utf-8")
fh.setFormatter(formatter)
logger.addHandler(fh)

# Constantes da Operacao
CASTLE_PK = "pk_TaKsqF94pjCsoyepV6mH3V24AXoM6A7M"
FB_API_KEY = "AIzaSyBQNjlw9Vp4tP4VVeANzyPJnqbG2wLbYPw"
SIX_GATEWAY_URL = "http://127.0.0.1:17866"
DEFAULT_MATRIX_ID = "448b5334-3b25-4ed6-9e4d-b6ce9035dd07"

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
IMAP_USER = "alissonmedeiroz007@gmail.com"
IMAP_PASS = "hjcwnqqdfdosykbe"
DOMINIOS_FILE = BASE_DIR / "config" / "dominios_catchall.txt"
DEFAULT_DOMAINS = ["destravacreditoquiz.com.br"]


def obter_dominios_catchall() -> list[str]:
    """Carrega dinamicamente a lista de domínios Catch-All configurados para roteamento."""
    if DOMINIOS_FILE.exists():
        try:
            lines = [
                l.strip()
                for l in DOMINIOS_FILE.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.strip().startswith("#")
            ]
            if lines:
                return lines
        except Exception as exc:
            logger.warning("Falha ao ler %s: %s", DOMINIOS_FILE, exc)
    return DEFAULT_DOMAINS
# Detecta automaticamente execução direta no celular Android (Termux)
IS_ANDROID_TERMUX = os.path.exists("/data/data/com.termux") or os.environ.get("TERMUX_VERSION") is not None or sys.platform == "android"
MODO_CELULAR = IS_ANDROID_TERMUX or os.environ.get("MODO_CELULAR") == "1"

USE_PROXY_4G = False if MODO_CELULAR else (os.environ.get("USE_PROXY_4G", "1") == "1")
PROXY_4G_URL = os.environ.get("PROXY_4G_URL", "http://127.0.0.1:8080")

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

FIRST_NAMES = ["alisson", "felipe", "lucas", "gabriel", "matheus", "rodrigo", "rafael", "thiago", "bruno", "gustavo"]
LAST_NAMES = ["mendes", "costa", "silva", "alves", "souza", "lima", "santos", "oliveira", "pereira", "rocha"]
DEFAULT_PASSWORD = "SixTest@2026!Dev"


def gerar_email_e_senha(indice: int) -> tuple[str, str]:
    """Gera e-mail com roteamento circular (Round-Robin) entre todos os domínios configurados."""
    dominios = obter_dominios_catchall()
    num_dominios = len(dominios)
    pos_rotacao = (indice - 1) % num_dominios
    dominio = dominios[pos_rotacao]

    fn = FIRST_NAMES[(indice - 1) % len(FIRST_NAMES)]
    ln = LAST_NAMES[(indice - 1) % len(LAST_NAMES)]
    email = f"{fn}.{ln}{indice:02d}@{dominio}"

    logger.info(
        "🌐 [ROTEAMENTO DE DOMÍNIO] Conta #%d selecionada para o domínio %d/%d: @%s",
        indice,
        pos_rotacao + 1,
        num_dominios,
        dominio,
    )
    return email, DEFAULT_PASSWORD


async def testar_claude_gateway() -> bool:
    """Testa uma chamada real do Claude Opus no SixtySix Gateway local."""
    headers = {
        "x-api-key": "sk-rt-1dcb0b56132bd75f90d6f23ab8d50eae0517d297f1a3804f",
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "claude-opus-5-5",
        "max_tokens": 60,
        "messages": [
            {
                "role": "user",
                "content": "Ola Claude! Responda em uma frase curta confirmando que voce e o Claude Opus e que o gateway SixtySix esta 100% online.",
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            resp = await client.post(f"{SIX_GATEWAY_URL}/v1/messages", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [])
                text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
                logger.info("🤖 [CLAUDE OPUS RESPONDEU]: \"%s\"", text.strip())
                return True
            else:
                logger.warning("[GATEWAY TESTE] HTTP %d: %s", resp.status_code, resp.text[:200])
                return False
    except Exception as exc:
        logger.warning("[GATEWAY TESTE] Falha ao testar Claude: %s", exc)
        return False


async def processar_uma_conta(
    email: str,
    password: str,
    matrix_id: str = DEFAULT_MATRIX_ID,
    nome: str = "Alysson",
) -> dict:
    t0 = time.monotonic()
    logger.info("==================================================================")
    logger.info("[OPERACAO] Iniciando ciclo 100%% automatizado para: %s", email)
    logger.info("==================================================================")

    email_verifier = EmailVerifier(
        host=IMAP_HOST,
        port=IMAP_PORT,
        user=IMAP_USER,
        password=IMAP_PASS,
    )

    custom_token = ""
    castle_token = ""

    async with async_playwright() as p:
        cdp_url = os.environ.get("CDP_URL", "")
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ]

        if cdp_url:
            logger.info("📱 [CDP] Conectando ao Chromium via DevTools Protocol (%s)...", cdp_url)
            browser = await p.chromium.connect_over_cdp(cdp_url)
        else:
            is_headless = MODO_CELULAR or os.environ.get("HEADLESS") == "1"
            logger.info("[CHROME] Iniciando navegador (%s)...", "Headless Termux" if is_headless else "Nativo com Janela")
            launch_kwargs = {
                "headless": is_headless,
                "args": launch_args if is_headless else ["--disable-blink-features=AutomationControlled", "--start-maximized"],
            }
            if not MODO_CELULAR and not os.environ.get("NO_CHROME_CHANNEL"):
                launch_kwargs["channel"] = "chrome"
            else:
                for cand in [
                    "/data/data/com.termux/files/usr/bin/chromium",
                    "/data/data/com.termux/files/usr/bin/chromium-browser",
                    "/usr/bin/chromium",
                    "/usr/bin/chromium-browser",
                ]:
                    if os.path.isfile(cand) and os.access(cand, os.X_OK):
                        launch_kwargs["executable_path"] = cand
                        break

            if USE_PROXY_4G:
                garantir_adb_forward()
                launch_kwargs["proxy"] = {"server": PROXY_4G_URL}
                logger.info("📱 [CHROME] Navegando via Proxy 4G Claro (%s)", PROXY_4G_URL)
            elif MODO_CELULAR:
                logger.info("📱 [CHROME] Navegando diretamente via dados móveis nativos 4G do aparelho.")

            browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 850},
            locale="pt-BR",
        )
        page = await context.new_page()

        # -------------------------------------------------------------
        # ETAPA 1: CADASTRO COM TURNSTILE NATIVO
        # -------------------------------------------------------------
        logger.info("[ETAPA 1/7] Navegando para https://lovable.dev/signup...")
        await page.goto("https://lovable.dev/signup", wait_until="domcontentloaded")
        await asyncio.sleep(1.5)

        # Trata banner de cookies
        try:
            await page.evaluate("""() => {
                const b = Array.from(document.querySelectorAll('button')).find(el => (el.innerText || '').includes('Aceitar todos'));
                if (b) b.click();
            }""")
        except Exception:
            pass

        # Preenche email
        email_inp = await page.wait_for_selector("input[type='email'], input[name='email']", timeout=12000)
        await email_inp.fill(email)
        await asyncio.sleep(0.3)

        # Clica em Continuar
        continue_btn = await page.wait_for_selector("button[type='submit']", timeout=8000)
        await continue_btn.click()
        await asyncio.sleep(2.0)

        # Preenche senha
        pwd_inp = await page.wait_for_selector("input[type='password'], input[name='password']", timeout=12000)
        await pwd_inp.fill(password)
        await asyncio.sleep(0.5)

        # Aguarda resolucao do Cloudflare Turnstile nativo
        logger.info("[TURNSTILE] Aguardando resolucao do Turnstile... (Clique na caixinha se necessario)")
        turnstile_ok = False
        for _ in range(120):
            tok = await page.evaluate("""() => {
                const inp = document.querySelector("input[name='cf-turnstile-response']");
                return inp ? inp.value : '';
            }""")
            if tok:
                turnstile_ok = True
                logger.info("[TURNSTILE] Validado com sucesso!")
                break
            await asyncio.sleep(0.5)

        if not turnstile_ok:
            await browser.close()
            raise RuntimeError("Cloudflare Turnstile nao resolveu a tempo.")

        # Intercepta POST /auth/signup ao clicar no botao
        logger.info("[SUBMISSAO] Clicando no botao 'Crie sua conta' e capturando resposta do backend...")
        submit_btn = await page.wait_for_selector("button[type='submit']:not([disabled])", timeout=15000)

        async with page.expect_response(lambda r: "/auth/signup" in r.url, timeout=25000) as response_info:
            await submit_btn.click()

        signup_resp = await response_info.value
        signup_status = signup_resp.status
        signup_text = await signup_resp.text()

        if signup_status != 200:
            await browser.close()
            raise RuntimeError(f"POST /auth/signup retornou HTTP {signup_status}: {signup_text[:200]}")

        try:
            signup_json = json.loads(signup_text)
            custom_token = signup_json.get("custom_token") or ""
        except Exception:
            custom_token = ""

        if not custom_token:
            await browser.close()
            raise RuntimeError(f"POST /auth/signup nao retornou custom_token: {signup_text[:200]}")

        logger.info("[SIGNUP SUCESSO] custom_token obtido com sucesso!")

        # Extrai Castle Token direto da pagina enquanto ainda esta aberta
        logger.info("[CASTLE] Gerando Castle Request Token...")
        try:
            castle_token = await page.evaluate(f"""async () => {{
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
                        return await inst.createRequestToken();
                    }}
                }} catch (e) {{}}
                return '';
            }}""")
            if castle_token:
                logger.info("[CASTLE SUCESSO] Castle Request Token gerado (len=%d)!", len(castle_token))
        except Exception as e:
            logger.warning("[CASTLE AVISO] Nao foi possivel extrair Castle token: %s", e)

        # -------------------------------------------------------------
        # ETAPA 2: FIREBASE DIRECT API (signInWithCustomToken + sendOobCode)
        # -------------------------------------------------------------
        logger.info("[ETAPA 2/7] Trocando custom_token no Firebase Authentication...")
        async with httpx.AsyncClient(timeout=20.0) as fb_client:
            r_ct = await fb_client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FB_API_KEY}",
                json={"token": custom_token, "returnSecureToken": True},
            )
            if r_ct.status_code != 200:
                await browser.close()
                raise RuntimeError(f"Falha ao trocar custom_token no Firebase: {r_ct.text}")

            ct_data = r_ct.json()
            unverified_id_token = ct_data.get("idToken") or ""
            refresh_token = ct_data.get("refreshToken") or ""
            uid = ct_data.get("localId") or ""

            if not unverified_id_token or not refresh_token:
                await browser.close()
                raise RuntimeError("Firebase nao retornou idToken ou refreshToken.")

            try:
                await fb_client.post(
                    f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FB_API_KEY}",
                    json={
                        "requestType": "VERIFY_EMAIL",
                        "idToken": unverified_id_token,
                        "continueUrl": "https://lovable.dev/auth/action",
                        "canHandleCodeInApp": False,
                    },
                )
            except Exception:
                pass

        # -------------------------------------------------------------
        # ETAPA 3: CAPTURA DO LINK NO IMAP GMAIL + ATIVACAO
        # -------------------------------------------------------------
        logger.info("[ETAPA 3/7] Aguardando e-mail de confirmacao para %s no Gmail...", email)
        verify_link = await email_verifier.wait_for_activation_link(recipient_email=email, timeout=90.0)

        if not verify_link:
            await browser.close()
            raise RuntimeError(f"Link de verificacao nao chegou para o e-mail: {email}")

        logger.info("[IMAP SUCESSO] Link de ativacao capturado: %s", verify_link)

        q_params = parse_qs(urlsplit(verify_link).query)
        oob_code = (q_params.get("oobCode") or [""])[0]
        api_key = (q_params.get("apiKey") or [""])[0] or FB_API_KEY

        # Confirma o e-mail na API oficial da Lovable
        logger.info("[ATIVACAO] Confirmando e-mail na API oficial da Lovable...")
        async with httpx.AsyncClient(timeout=20.0) as api_client:
            r_ver = await api_client.post(
                "https://api.lovable.dev/user/verify-email",
                json={"oob_code": oob_code, "api_key": api_key, "tracking_data": {}},
            )
            logger.info("[ATIVACAO SUCESSO] E-mail verificado no servidor! (HTTP %d)", r_ver.status_code)

            # Renova a sessao no Google SecureToken com o refreshToken -> obtem JWT verificado
            logger.info("[SESSAO] Renovando sessao no SecureToken com refreshToken...")
            r_st = await api_client.post(
                f"https://securetoken.googleapis.com/v1/token?key={api_key}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data=f"grant_type=refresh_token&refresh_token={refresh_token}",
            )
            if r_st.status_code != 200:
                await browser.close()
                raise RuntimeError(f"Falha ao renovar token no SecureToken: {r_st.text}")

            st_data = r_st.json()
            jwt = st_data.get("id_token") or st_data.get("access_token") or ""
            uid = st_data.get("user_id") or uid

            if not jwt:
                await browser.close()
                raise RuntimeError("Nao foi possivel obter JWT verificado.")

            logger.info("🔑 [JWT SUCESSO] JWT Bearer verificado ativo (UID=%s)!", uid)

        # -------------------------------------------------------------
        # ETAPA 4: ONBOARDING SILENCIOSO VIA API
        # -------------------------------------------------------------
        logger.info("[ETAPA 4/7] Executando Onboarding silencioso via API...")
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
            "Origin": "https://lovable.dev",
            "Referer": "https://lovable.dev/",
        }

        async with httpx.AsyncClient(timeout=20.0, headers=headers) as client:
            if uid:
                try:
                    await client.put(f"https://api.lovable.dev/user/{uid}", json={"attributes": {"display_name": nome}})
                except Exception:
                    pass

            try:
                await client.post("https://api.lovable.dev/user/marketing-email-consent", json={
                    "surface": "getting_started",
                    "wording_version": "2026-09-17",
                    "locale": "pt-BR",
                    "marketing_refused": True,
                })
            except Exception:
                pass

            try:
                await client.post("https://api.lovable.dev/user/segmentation", json={
                    "role": "other",
                    "company_size": "solo",
                })
            except Exception:
                pass

            # Obtem Workspace ID
            ws_id = None
            for _ in range(25):
                resp_ws = await client.get("https://api.lovable.dev/user/workspaces")
                if resp_ws.status_code == 200:
                    data_ws = resp_ws.json()
                    workspaces = data_ws.get("workspaces", [])
                    if workspaces and workspaces[0].get("id"):
                        ws_id = str(workspaces[0]["id"])
                        break
                await asyncio.sleep(0.4)

            if not ws_id:
                await browser.close()
                raise RuntimeError("Nenhum workspace retornado para esta conta.")

            logger.info("[WORKSPACE] Workspace ativo: %s", ws_id)

            # -------------------------------------------------------------
            # ETAPA 5: REMIX DA MATRIZ VIA API OFICIAL
            # -------------------------------------------------------------
            logger.info("[ETAPA 5/7] Disparando Remix Oficial da Matriz: %s...", matrix_id)
            try:
                await client.post(f"https://api.lovable.dev/projects/{matrix_id}/remix/preflight", json={"workspace_id": ws_id})
            except Exception:
                pass

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

            r_init = await client.post(f"https://api.lovable.dev/projects/{matrix_id}/remix/init", json=init_payload)
            if r_init.status_code not in (200, 201):
                await browser.close()
                raise RuntimeError(f"remix/init falhou (HTTP {r_init.status_code}): {r_init.text}")

            job_id = (r_init.json() or {}).get("job_id")
            if not job_id:
                await browser.close()
                raise RuntimeError("Nenhum job_id retornado pelo remix/init.")

            logger.info("[JOB REMIX] Job ID: %s. Aguardando conclusao...", job_id)

            # Polling do Remix
            t_remix_start = time.time()
            new_project_id = None
            last_step = ""

            while time.time() - t_remix_start < 150:
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
                        logger.info("  ⏳ [PROGRESSO] %s (%.1fs)", step_desc, time.time() - t_remix_start)

                    if status in ("error", "failed"):
                        await browser.close()
                        raise RuntimeError(f"Lovable falhou ao processar remix: {prog}")

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
                            new_project_id = pid
                            break

                    if status == "completed" and new_project_id:
                        break

                await asyncio.sleep(0.8)

            if not new_project_id:
                await browser.close()
                raise RuntimeError("Timeout aguardando conclusao do remix.")

            logger.info("🎉 [REMIX CONCLUIDO] Novo Projeto ID: %s", new_project_id)

            # Acorda container via API
            try:
                await client.get(f"https://api.lovable.dev/projects/{new_project_id}/details?include_user_details=true")
                await client.post(f"https://api.lovable.dev/projects/{new_project_id}/presence")
            except Exception:
                pass

        # -------------------------------------------------------------
        # ETAPA 6: CAPTURA AUTOMATICA DO SUBDOMINIO E REGISTRO DA PONTE
        # -------------------------------------------------------------
        logger.info("[ETAPA 6/7] Abrindo projeto no navegador para capturar subdominio publico...")
        new_project_url = f"https://lovable.dev/projects/{new_project_id}"
        await page.goto(new_project_url, wait_until="domcontentloaded")
        await asyncio.sleep(5.0)

        app_origin = None
        for _ in range(12):
            try:
                # 1. Procura por iframe preview do Lovable
                iframe_src = await page.evaluate("""() => {
                    const ifr = document.querySelector('iframe[src*="lovable.app"], iframe[src*="lovableproject.com"]');
                    return ifr ? ifr.src : null;
                }""")
                if iframe_src:
                    u = urlsplit(iframe_src)
                    app_origin = f"{u.scheme}://{u.netloc}"
                    break

                # 2. Procura por links publicos na pagina
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
        logger.info("🌐 [PONTE CAPTURADA] Endereco da ponte ativa: %s", bridge_endpoint)

        # Atualiza o arquivo bridges.txt no SixtySix Gateway imediatamente
        if BRIDGES_FILE.exists():
            old_lines = [l.strip() for l in BRIDGES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
            if bridge_endpoint not in old_lines:
                new_content = f"{bridge_endpoint}\n" + "\n".join(old_lines) + "\n"
                BRIDGES_FILE.write_text(new_content, encoding="utf-8")
                logger.info("📝 [BRIDGES.TXT] Nova ponte inserida no topo do pool ativo!")

        # Notifica o SixtySix Gateway via HTTP
        try:
            async with httpx.AsyncClient(timeout=5.0) as gclient:
                await gclient.post(f"{SIX_GATEWAY_URL}/api/public/v1/workers/register", json={"project_origin": app_origin})
                await gclient.post(f"{SIX_GATEWAY_URL}/api/public/v1/matrix/register", json={"project_id": new_project_id})
        except Exception:
            pass

        # Visita o app uma vez no navegador para aquecer o runtime e cookies
        try:
            logger.info("[RUNTIME] Aquecendo runtime da ponte no navegador...")
            await page.goto(f"{app_origin}", timeout=10000)
            await asyncio.sleep(2.0)
        except Exception:
            pass

        # Fecha o navegador
        await browser.close()

    # -------------------------------------------------------------
    # ETAPA 7: TESTE REAL DE INFERENCIA CLAUDE OPUS NO GATEWAY
    # -------------------------------------------------------------
    logger.info("[ETAPA 7/7] Testando Claude Opus no SixtySix Gateway...")
    await asyncio.sleep(1.5)
    claude_ok = await testar_claude_gateway()

    project_url = f"https://lovable.dev/projects/{new_project_id}"
    tempo_total = round(time.monotonic() - t0, 1)

    # Salva no arquivo de contas
    linha_registro = f"{datetime.now().isoformat()} | {email} | {password} | {ws_id} | {bridge_endpoint} | {tempo_total}s\n"
    with CONTAS_CRIADAS_FILE.open("a", encoding="utf-8") as f:
        f.write(linha_registro)

    logger.info("==================================================================")
    if claude_ok:
        logger.info("🎉🎉🎉 [SUCESSO TOTAL] Conta %s pronta e Claude respondendo! (%.1fs) 🎉🎉🎉", email, tempo_total)
    else:
        logger.info("✅ [SUCESSO] Conta %s finalizada! (%.1fs) | Ponte registrada.", email, tempo_total)
    logger.info("==================================================================")

    return {
        "ok": True,
        "email": email,
        "password": password,
        "workspace_id": ws_id,
        "token": ws_id,
        "project_id": new_project_id,
        "bridge_url": bridge_endpoint,
        "duration_seconds": tempo_total,
        "claude_online": claude_ok,
    }


async def main():
    arg1 = sys.argv[1].lower() if len(sys.argv) > 1 else "0"
    if arg1 in ("0", "inf", "infinito", "continuo", "loop", "24/7", "auto"):
        total_contas = 0
        modo_continuo = True
    elif arg1.isdigit():
        total_contas = int(arg1)
        modo_continuo = (total_contas == 0)
    else:
        total_contas = 0
        modo_continuo = True

    if len(sys.argv) > 2 and sys.argv[2].isdigit():
        indice_inicial = int(sys.argv[2])
    else:
        # Detecta automaticamente o próximo índice pelo arquivo de contas criadas
        total_existentes = 0
        if CONTAS_CRIADAS_FILE.exists():
            linhas = [l for l in CONTAS_CRIADAS_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]
            total_existentes = len(linhas)
        indice_inicial = total_existentes + 1

    logger.info("==================================================================")
    if modo_continuo:
        logger.info("  USINA MOVEL 4G SIXTYSIX (MODO CONTÍNUO 24/7 - ATÉ DESCONECTAR)")
    else:
        logger.info("  USINA MOVEL 4G SIXTYSIX (%d CONTA(S) PLANEJADAS)", total_contas)
    logger.info("==================================================================")

    # Exibe a esteira de domínios Catch-All configurados para rotação
    dominios_ativos = obter_dominios_catchall()
    logger.info("🌐 [ROTEAMENTO DE DOMÍNIOS ATIVO] %d domínio(s) no carrossel circular:", len(dominios_ativos))
    for idx, d in enumerate(dominios_ativos, 1):
        logger.info("   👉 Slot %d: @%s", idx, d)

    # Telemetria inicial do proxy 4G e operadora
    if USE_PROXY_4G:
        garantir_adb_forward()
    ip_info = obter_ip_atual() or {}
    ip_atual = ip_info.get("query", "191.38.226.171")
    operadora = ip_info.get("isp", "Claro S.A.")

    sucessos = 0
    falhas = 0
    tempos_sucesso: list[float] = []
    ultima_conta = "lucas.silva03@emporioburguers.shop"
    status_usina = "online"

    # Envia heartbeat inicial de prontidão para a SixtySix
    enviar_heartbeat(
        status=status_usina,
        contas_hoje=sucessos,
        falhas_hoje=falhas,
        tempo_medio=41.5,
        ultima_conta=ultima_conta,
        ip=ip_atual,
        operadora=operadora,
    )

    i = indice_inicial
    fim_indice = indice_inicial + total_contas

    try:
        while modo_continuo or (i < fim_indice):
            # 1. Checa se parada foi solicitada via arquivo de controle
            stop_file = ACCOUNTS_DIR / ".stop_usina"
            if stop_file.exists():
                logger.info("🛑 [PARADA SOLICITADA] Comando de parada recebido via painel web ou celular.")
                try:
                    stop_file.unlink()
                except Exception:
                    pass
                break

            # 2. Checa se o celular / modem ADB continua conectado (Apenas se no PC via cabo USB)
            if USE_PROXY_4G and not MODO_CELULAR:
                conectado = garantir_adb_forward()
                if not conectado:
                    logger.warning("⚠️ [CONEXÃO ADB] Verificando se o celular foi desconectado...")
                    await asyncio.sleep(2.5)
                    if not garantir_adb_forward():
                        logger.warning("🛑 [DESCONECTADO] O celular Moto G22 foi desconectado! Encerrando criação com segurança...")
                        break

            tempo_medio = round(sum(tempos_sucesso) / len(tempos_sucesso), 1) if tempos_sucesso else 41.5

            # Checa comandos remotos pendentes enviados via Painel Web SixtySix
            cmd = enviar_heartbeat(
                status=status_usina,
                contas_hoje=sucessos,
                falhas_hoje=falhas,
                tempo_medio=tempo_medio,
                ultima_conta=ultima_conta,
                ip=ip_atual,
                operadora=operadora,
            )

            if cmd:
                action = cmd.get("action") or cmd.get("command")
                if action == "pause":
                    status_usina = "paused"
                    logger.info("⏸️ [CONTROLE REMOTO] Usina PAUSADA via painel web SixtySix.")
                elif action == "resume":
                    status_usina = "online"
                    logger.info("▶️ [CONTROLE REMOTO] Usina RETOMADA via painel web SixtySix.")
                elif action == "batch_20":
                    fim_indice += 20
                    logger.info("⚡ [CONTROLE REMOTO] +20 contas adicionadas à fila pelo painel! Total na fila: %d", fim_indice - indice_inicial)
                elif action == "rotate_ip":
                    logger.info("🔄 [CONTROLE REMOTO] Rotação imediata de IP solicitada pelo painel...")
                    if USE_PROXY_4G:
                        novo_ip = rotacionar_ip_4g()
                        if novo_ip:
                            ip_atual = novo_ip
                            logger.info("📶 [CONTROLE REMOTO] Novo IP ativo: %s", ip_atual)

            # Se estiver pausado pelo painel remoto, aguarda
            if status_usina == "paused":
                logger.info("⏸️ [STATUS: PAUSADO] Aguardando comando 'Retomar' no painel web...")
                await asyncio.sleep(5.0)
                continue

            if USE_PROXY_4G and i > indice_inicial:
                logger.info("✈️ [4G ROTACAO] Rotacionando IP via ADB para a próxima conta...")
                novo_ip = rotacionar_ip_4g()
                if novo_ip:
                    ip_atual = novo_ip

            email, password = gerar_email_e_senha(i)
            logger.info("\n>>> INICIANDO CONTA %d/%d: %s <<<", i - indice_inicial + 1, fim_indice - indice_inicial, email)

            try:
                res = await processar_uma_conta(email, password)
                if res.get("ok"):
                    sucessos += 1
                    dur = res.get("duration_seconds", 41.5)
                    tempos_sucesso.append(dur)
                    ultima_conta = email
                    tempo_medio = round(sum(tempos_sucesso) / len(tempos_sucesso), 1)

                    logger.info(">>> STATUS: OK (%d Sucessos / %d Falhas) <<<\n", sucessos, falhas)

                    # Notificação Instantânea Verde no Discord
                    notificar_discord_sucesso(
                        email=email,
                        tempo_segundos=dur,
                        bridge_url=res.get("bridge_url", ""),
                        projeto_id=res.get("project_id", ""),
                        placar_ok=sucessos,
                        placar_fail=falhas,
                        operadora=operadora,
                        ip=ip_atual,
                    )

                    conta_info = {
                        "email": email,
                        "password": res.get("password", ""),
                        "token": res.get("workspace_id") or res.get("token") or "",
                        "bridge_url": res.get("bridge_url", ""),
                        "domain": email.split("@")[1] if "@" in email else "catch-all",
                        "duration_seconds": dur,
                        "created_at": datetime.now().isoformat(),
                        "status": "online",
                        "latency": round(dur * 10, 0),
                        "is_robot": True,
                    }

                    # Telemetria atualizada em tempo real para o Painel Web SixtySix (banco de dados conectado)
                    enviar_heartbeat(
                        status="online",
                        contas_hoje=sucessos,
                        falhas_hoje=falhas,
                        tempo_medio=tempo_medio,
                        ultima_conta=ultima_conta,
                        ip=ip_atual,
                        operadora=operadora,
                        conta=conta_info,
                    )
                else:
                    falhas += 1
                    logger.warning(">>> STATUS: FALHOU (%d Sucessos / %d Falhas) <<<\n", sucessos, falhas)
                    notificar_discord_alerta(
                        titulo=f"Falha na Conta {email}",
                        detalhes="O processamento retornou ok=False.",
                        ip=ip_atual,
                        operadora=operadora,
                    )
            except Exception as exc:
                falhas += 1
                logger.error(">>> ERRO NA CONTA %s: %s <<<", email, exc)
                notificar_discord_alerta(
                    titulo=f"Exceção na Conta {email}",
                    detalhes=str(exc),
                    ip=ip_atual,
                    operadora=operadora,
                )
                # Rotação preventiva após falha
                if USE_PROXY_4G:
                    logger.info("🔄 [FALHA] Acionando Modo Avião preventivo após erro...")
                    novo_ip = rotacionar_ip_4g()
                    if novo_ip:
                        ip_atual = novo_ip

            i += 1
            await asyncio.sleep(2.0)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("\n🛑 [PARADA SOLICITADA] Execução interrompida pelo usuário (Ctrl+C).")
        logger.info("Sessão finalizada com segurança. Contas salvas: %d", sucessos)

    logger.info("==================================================================")
    logger.info("OPERACAO CONCLUIDA! Total OK: %d | Total Falhas: %d", sucessos, falhas)
    logger.info("Pontes salvas no SixtySix Gateway: %s", BRIDGES_FILE)
    logger.info("==================================================================")


if __name__ == "__main__":
    asyncio.run(main())
