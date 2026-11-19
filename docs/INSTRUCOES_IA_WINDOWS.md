# Instruções para a IA no PC Windows (Copiar e Colar)

> **Como usar:** Quando abrir o chat com a IA no PC Windows, copie todo o texto abaixo e cole no primeiro comando.

---

```text
Olá! Você está assumindo a continuidade do projeto QA Onboarding Automation da SixtySix aqui nesta máquina Windows.

Nosso objetivo de hoje é:
1. Conectar a automação ao AdsPower (plano pago com perfis e proxies reais).
2. Criar contas em massa na Lovable (https://lovable.dev/signup) usando nosso domínio próprio (@sixtysix.online).
3. Interceptar automaticamente os e-mails com links de validação e ativar todas as contas criadas.
4. Notificar o progresso e relatórios no canal #relatorios-qa do nosso Discord via Webhook.

---

### 1. REPOSITÓRIO E ESTRUTURA JÁ PRONTA NO GITHUB
O código já foi 100% desenvolvido, testado (23 testes passando no pytest) e commitado no GitHub.
* Repositório: https://github.com/Alysontrx/qa-onboarding-automation.git
* Branch: main

Arquivos chave do projeto:
* main.py: Ponto de entrada CLI e orquestrador geral.
* config/settings.py: Configurações centralizadas via .env e seletores da Lovable.
* core/adspower.py: Cliente assíncrono para a Local API do AdsPower (porta 50325).
* core/browser_manager.py: Gerenciador CDP para conectar aos navegadores do AdsPower.
* core/onboarding.py: Automação do formulário em 2 etapas da Lovable (cookies -> e-mail -> senha -> submit -> ativação).
* core/email_verifier.py: Leitor IMAP assíncrono para pegar o link de ativação via Catch-All da Cloudflare.
* core/reporter.py: Gera reports/resultados.csv, reports/resumo.json, calcula p95 e envia ao Discord com prints de eventuais erros.
* data/usuarios.csv: Arquivo CSV com a lista de perfis e e-mails @sixtysix.online.
* listar_perfis_adspower.py: Script que puxa os perfis do AdsPower e popula o usuarios.csv.
* setup_windows.bat: Script de instalação automática do ambiente no Windows.
* iniciar_windows.bat: Menu de 1 clique para rodar, testar ou sincronizar perfis no Windows.
* check_env.py: Script de diagnóstico rápido de portas e AdsPower.
* docs/CONTEXTO_PROJETO.md: Contexto e playbook técnico completo.

---

### 2. O QUE VOCÊ DEVE FAZER AGORA (PASSO A PASSO):

Passo 1: Diagnóstico do Ambiente
Execute `python check_env.py` ou verifique se o ambiente virtual .venv está ativo e se o aplicativo do AdsPower está aberto com a Local API ativa na porta 50325 (http://127.0.0.1:50325).

Passo 2: Sincronizar Perfis do AdsPower
Rode:
python listar_perfis_adspower.py --sync-csv --dominio sixtysix.online
Isso vai consultar a lista de navegadores criados no AdsPower e associar automaticamente um e-mail @sixtysix.online para cada um dentro de data/usuarios.csv.

Passo 3: Conferir as credenciais no .env
Verifique se o arquivo .env contém:
* USE_ADSPOWER=true
* ONBOARDING_URL=https://lovable.dev/signup
* VERIFY_EMAIL=true
* IMAP_HOST=imap.gmail.com
* IMAP_USER=<e-mail_do_gmail_que_recebe_o_catch_all>
* IMAP_PASSWORD=<senha_de_app_do_google>
(Se ainda não estiver configurado o e-mail de leitura, me pergunte para preenchermos).

Passo 4: Executar a Automação
Execute os cadastros e ativações em massa com:
python main.py --use-adspower --concurrency 2
(Ou através do menu interativo iniciar_windows.bat escolhendo a Opção [1]).

Passo 5: Validar a Execução e Relatório
Confirme se os cadastros foram concluídos, se as ativações foram validadas e verifique o envio do relatório para o canal do Discord #relatorios-qa.

Por favor, comece executando o Passo 1 (diagnóstico) e me diga o status atual da máquina e do AdsPower!
```
