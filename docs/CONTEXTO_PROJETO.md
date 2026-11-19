# Contexto do Projeto, Playbook e Especificação M2M

Este documento unifica **100% do contexto técnico, arquitetura, histórico, Playbook Operacional e Contrato de Integração Sistema-a-Sistema (M2M)** do projeto **QA Onboarding Automation**, servindo de guia completo tanto para humanos quanto para outros sistemas, orquestradores e assistentes de IA.

---

## 1. Visão Geral e Propósito

* **Objetivo:** Framework profissional em Python 3.11+ para automação de onboarding, testes de carga, criação e ativação automática de contas em massa e validação de confiabilidade de aplicações web.
* **Modo Híbrido:**
  * **AdsPower Local API:** Conexão direta via Chrome DevTools Protocol (CDP) aos perfis do AdsPower com fingerprints e proxies isolados.
  * **Playwright Local:** Execução isolada em Chromium nativo, permitindo testes sem depender do AdsPower aberto (ideal para CI/CD e desenvolvimento local).
* **Verificação e Ativação de E-mail Automática:**
  * Suporte nativo a fluxo com link de ativação via **Catch-All (Cloudflare Email Routing)** e cliente IMAP assíncrono (`core/email_verifier.py`).
  * O robô submete o formulário, aguarda a chegada do e-mail, extrai o link de ativação, navega até a URL no mesmo navegador e confirma a ativação.
* **Segurança:** Senhas nunca são expostas em logs, terminal ou relatórios (mascaramento estrito com `UserData.masked_password`).
* **Confiabilidade:** Zero processos órfãos — todas as abas e instâncias do AdsPower são encerradas ao final de cada teste ou sob interrupção graciosa (SIGINT/SIGTERM).

---

## 2. Playbook Operacional (Fluxo Ponta a Ponta)

```
[1. Massa de Dados] ──> [2. Gestão de Navegador] ──> [3. Criação de Conta] ──> [4. Ativação por E-mail] ──> [5. Relatórios & Discord]
   (csv_loader)             (browser_manager)               (onboarding)               (email_verifier)                 (reporter)
        │                          │                             │                            │                             │
  Valida e mascara          Abre via AdsPower             Preenche campos e            Intercepta link de            Gera CSV, JSON e envia
    credenciais              (CDP) ou Local               submete formulário           ativação e confirma           embed + anexos ao Discord
```

### Como a Esteira se Complementa na Prática:
1. **Dados alimentam a Automação:** `csv_loader.py` valida e-mails no padrão RFC e bloqueia entradas inconsistentes antes de abrir navegadores.
2. **Concorrência protege o Servidor:** `executor.py` dosa quantos navegadores rodam juntos via semáforos (`MAX_CONCURRENCY`) e aplica espaçamento (`RATE_LIMIT_DELAY`).
3. **AdsPower complementa o Playwright:** O AdsPower gerencia as impressões digitais dos perfis e proxies, enquanto o Playwright comanda as ações da tela via CDP em alta velocidade.
4. **Email Verifier complementa o Onboarding:** Caso a aplicação exija confirmação de e-mail (`VERIFY_EMAIL=true`), o `email_verifier.py` captura a URL de ativação em tempo real e a abre no mesmo perfil.
5. **Screenshots complementam os Logs:** Quando um cadastro ou ativação falha, a imagem da tela no instante do erro é gravada em `logs/screenshots/` e enviada como anexo no Discord.
6. **Métricas complementam a Tomada de Decisão:** `reports/resumo.json` entrega taxa de sucesso, tempos médios e **Percentil 95 (p95)**.

---

## 3. Criação e Ativação de Contas com Domínio Próprio (`@sixtysix.online`)

### 3.1. Arquitetura de Recebimento de E-mails (Catch-All Gratuito)
Como o domínio `sixtysix.online` está sob a Cloudflare (`gannon.ns.cloudflare.com` / `mona.ns.cloudflare.com`):

1. **Ativar Cloudflare Email Routing:**
   * No painel da Cloudflare ➔ Domínio `sixtysix.online` ➔ **Email Routing** ➔ Ativar.
   * Em **Routing Rules** ➔ ativar a regra **Catch-all rule** apontando para o seu e-mail de leitura (ex: `seuemail@gmail.com`).
   * A partir deste momento, qualquer e-mail enviado para `*@sixtysix.online` (ex: `alyson.01@sixtysix.online`) é entregue imediatamente na caixa central.

2. **Como o Robô Ativa a Conta Sozinho:**
   * O robô cria a conta no formulário web.
   * O site envia o e-mail de ativação.
   * O módulo `core/email_verifier.py` conecta no Gmail via IMAP (porta 993 SSL), busca a mensagem para aquele destinatário, decodifica o HTML e extrai o link de ativação via regex.
   * O Playwright navega para a URL no mesmo navegador, clica em botões de confirmação se houver e valida o sucesso.

---

## 4. Estrutura de Arquivos e Componentes

| Arquivo / Diretório | Responsabilidade |
| :--- | :--- |
| `config/settings.py` | Leitura centralizada de variáveis de ambiente (`.env`), seletores de UI e timeouts |
| `core/adspower.py` | Cliente assíncrono para a Local API do AdsPower (porta `50325`) |
| `core/browser_manager.py` | Conexão CDP com AdsPower ou fallback para Playwright Chromium local |
| `core/csv_loader.py` | Validação, deduplicação e mascaramento de credenciais |
| `core/onboarding.py` | Execução do formulário, detecção de erros visuais e fluxo de ativação |
| `core/email_verifier.py` | Leitura IMAP assíncrona, extração de URLs de validação e desescape de entidades |
| `core/executor.py` | Controle de concorrência (`asyncio.Semaphore`), retries com backoff e cancelamento gracioso |
| `core/reporter.py` | Geração de CSV, JSON, cálculo de p95 e despacho multipart para Webhook do Discord |
| `data/gerar_usuarios.py` | Utilitário CLI para geração sintética de contas com o domínio `@sixtysix.online` |
| `listar_perfis_adspower.py` | Utilitário para consultar perfis no AdsPower e sincronizar o `data/usuarios.csv` |
| `iniciar_windows.bat` | Menu interativo de 1 clique para Windows (Executar, Testar, Sincronizar) |
| `setup_windows.bat` | Instalador automático de dependências e ambiente virtual no Windows |
| `iniciar_mac.command` | Inicializador interativo para macOS |
| `setup.sh` | Instalador automático de ambiente para Linux/macOS |
| `check_env.py` | Diagnóstico automático de portas, AdsPower e ambiente |
| `tests/` | Suíte com 23 testes unitários e de integração cobrindo 100% dos componentes |

---

## 5. Especificação de Integração Sistema-a-Sistema (M2M Contract)

Para que outro sistema, bot, IA ou orquestrador automatizado converse com este framework:

### 5.1. Acoplamento via CLI / Subprocess
```bash
python main.py \
  --csv /caminho/para/dados.csv \
  --url https://seu-dominio.com/register \
  --concurrency 2 \
  --timeout 10000 \
  --use-adspower
```

* **Códigos de Saída (Exit Codes):**
  * `0`: Sucesso total (todos os registros processados com 0 falhas).
  * `1`: Ocorreu falha funcional (`FAILED`) ou timeout (`TIMEOUT`).
  * `130`: Interrompido por sinal SIGINT/SIGTERM (encerramento gracioso).

### 5.2. Contrato de Entrada (Input Payload - CSV)
Formato do arquivo `data/usuarios.csv`:
```csv
profile_id,email,password,name
1,teste001@sixtysix.online,SenhaSegura123!,Usuario Teste 1
2,teste002@sixtysix.online,SenhaSegura123!,Usuario Teste 2
```
* `profile_id`: Número do perfil do AdsPower (coluna `Nº`) ou ID alfanumérico.
* `email`: Endereço de e-mail a registrar.
* `password`: Senha para o cadastro.
* `name`: Nome a ser preenchido.

### 5.3. Contrato de Saída (Output Payload - JSON Consumível)
Arquivo **`reports/resumo.json`**:
```json
{
  "total_tests": 4,
  "success_count": 4,
  "failure_count": 0,
  "timeout_count": 0,
  "profile_error_count": 0,
  "connection_error_count": 0,
  "success_rate_percent": 100.0,
  "avg_duration_ms": 722.44,
  "p95_duration_ms": 931.83,
  "per_profile_summary": {
    "1": [
      {
        "email": "te***@sixtysix.online",
        "status": "SUCCESS",
        "step": "COMPLETE",
        "duration_ms": 720.15,
        "error_message": null
      }
    ]
  }
}
```

* **Dicionário de Status:**
  * `SUCCESS`: Cadastro e ativação concluídos e validados na interface.
  * `FAILED`: Rejeitado pelo formulário da web (ex: e-mail já cadastrado).
  * `TIMEOUT`: Algum elemento ou e-mail de ativação demorou mais que o timeout configurado.
  * `PROFILE_ERROR`: Falha de inicialização do perfil no AdsPower.
  * `CONNECTION_ERROR`: Impossibilidade de conectar à API Local do AdsPower.

---

## 6. Configurações de Ambiente (`.env`)

```env
# AdsPower Local API
ADSPOWER_URL=http://127.0.0.1:50325
ADSPOWER_API_KEY=
USE_ADSPOWER=true

# Aplicação Alvo
ONBOARDING_URL=https://sixtysix.online/register

# Concorrência e Timeouts
MAX_CONCURRENCY=2
DEFAULT_TIMEOUT=15000
MAX_RETRIES=2
RATE_LIMIT_DELAY=1.0
HEADLESS=false

# Notificações do Discord (Canal #relatorios-qa)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1572780922586144801/FYgYdd0_G1pfnddYJoUHNwr0ytvPRfybfcvffymXdZxyTKJuMWT8KB-G0u7ojQOFczDU

# Verificação Automática de E-mail (Catch-All)
VERIFY_EMAIL=true
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=seuemail@gmail.com
IMAP_PASSWORD=sua_senha_de_app_do_google
EMAIL_WAIT_TIMEOUT=60
EMAIL_POLL_INTERVAL=3.0
```

---

## 7. Como Executar no PC Windows (Guia Rápido)

1. **Baixar e Instalar:**
   ```cmd
   git clone https://github.com/Alysontrx/qa-onboarding-automation.git
   cd qa-onboarding-automation
   setup_windows.bat
   ```
2. **Ativar o AdsPower:**
   * Abrir o AdsPower ➔ **Configurações ⚙️ ➔ Local API** ➔ Ativar chave seletora (porta `50325`).
3. **Executar a Automação:**
   * Dar dois cliques no arquivo `iniciar_windows.bat`.
   * **Opção [3]:** Sincroniza os perfis do AdsPower gerando os e-mails `@sixtysix.online` automaticamente.
   * **Opção [1]:** Roda a criação e ativação em massa com envio de relatórios e fotos de erros para o Discord!
