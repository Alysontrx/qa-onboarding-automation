# Histórico da Conversa e Decisões Tomadas

Este documento registra os principais diálogos, esclarecimentos de requisitos e soluções aplicadas durante o desenvolvimento do framework.

---

### 1. Solicitação Inicial e Definição de Escopo
* **Demanda:** Criar um framework completo de QA para teste de onboarding com Playwright + AdsPower Local API, Python 3.11+, CSV de entrada, gerenciamento de concorrência, relatórios estatísticos (taxa de sucesso, média, p95) e interface de terminal com Rich.
* **Diretriz de Segurança:** Sem técnicas de evasão de bot, com foco estrito em automação de homologação/QA, proteção de credenciais e encerramento seguro de navegadores para evitar processos órfãos.

---

### 2. Dúvidas Frequentes e Respostas Resolvidas

#### P: "O que já está funcionando nesses códigos para eu instalar em outro PC?"
* **R:** Todos os módulos do framework foram implementados e testados com 100% de aprovação (17 testes do Pytest). Para levar a outro PC, basta copiar todo o repositório (exceto a pasta `.venv`), rodar `pip install -r requirements.txt`, `playwright install chromium` e executar `python main.py`.

#### P: "Cadê a Local API e o ID do perfil no AdsPower?" (Baseado na interface visual do AdsPower)
* **Local API:** No menu do aplicativo (`Preferências` ou clicando no perfil do usuário no canto superior direito), aba **Local API** ➔ ativar chave seletora ➔ confirmar porta `50325`.
* **Identificador de Perfil:** Na lista de perfis do AdsPower, a coluna **`Nº`** indica o número de série (ex: `1`). O código foi configurado para aceitar tanto esse número de série simples (`serial_number=1`) quanto o ID alfanumérico interno (`user_id`).

#### P: "Quero usar para criar contas no meu domínio, está certo?"
* **R:** 
  - **Cenário A (Criar usuários em formulário web do domínio):** Sim, está 100% correto. O robô acessa a URL configurada, preenche o formulário e valida a confirmação de criação da conta.
  - **Cenário B (Criar caixas postais de e-mail no servidor):** Se for para provisionar caixas de e-mail diretamente no servidor (cPanel/Postfix/Google Workspace), o ideal é usar a API oficial do painel de e-mail por ser mais rápida e direta.

---

### 3. Principais Comandos de Execução

```bash
# Rodar todos os testes automatizados
pytest -v

# Rodar modo local sem AdsPower (com interface visível para debug)
python main.py --local --no-headless --url http://127.0.0.1:8080/register

# Rodar com AdsPower ativado
python main.py --use-adspower --concurrency 2

# Testar se CSV e configurações estão válidas sem abrir navegadores
python main.py --dry-run
```

