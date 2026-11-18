# Contexto Geral do Projeto e Histórico de Desenvolvimento

Este documento foi gerado para fornecer **100% de contexto** do projeto para desenvolvedores, analistas de QA e assistentes de IA em qualquer outro computador.

---

## 1. Visão Geral e Propósito

* **Objetivo Principal:** Desenvolver um framework de QA em Python de nível sênior para testar a escalabilidade, resiliência e performance do fluxo de onboarding e registro de usuários em aplicações web.
* **Escopo:** Automação de navegadores reais via **Playwright** integrado à **AdsPower Local API** (usando Chrome DevTools Protocol - CDP), com suporte a fallback para **Chromium Local isolado**.
* **Caso de Uso:** Realizar testes de carga e onboarding automatizado em massa, garantindo relatórios estatísticos completos (taxa de sucesso, tempo médio, percentil 95 - p95) e segurança absoluta de senhas/credenciais.

---

## 2. Decisões de Arquitetura e Tecnologias

### Stack Técnica:
* **Python 3.11+** (testado e validado em Python 3.13)
* **Playwright (Async API):** Controle de instâncias de navegadores via CDP ou processo local.
* **HTTPX (AsyncClient):** Comunicação REST de alta performance com a Local API do AdsPower.
* **Rich:** Interface de linha de comando com tabelas, painéis e barra de progresso em tempo real.
* **Pytest & Pytest-Asyncio:** Suite com 17 testes automatizados cobrindo todos os módulos.
* **Python-Dotenv:** Parametrização desacoplada através do arquivo `.env`.

### Estrutura Modular:
* `config/settings.py`: Centraliza todas as configurações, caminhos e seletores da interface (`data-testid`).
* `core/adspower.py`: Gerencia o ciclo de vida dos navegadores no AdsPower (verificação de status, abertura de abas, captura do WebSocket `ws.puppeteer`, encerramento e prevenção de processos órfãos). Aceita tanto `user_id` alfanumérico quanto o número de série da coluna `Nº` (ex: `1`).
* `core/browser_manager.py`: Abstração para conexão CDP (AdsPower) ou inicialização de Chromium nativo do Playwright.
* `core/csv_loader.py`: Ingestão de `data/usuarios.csv`, validação rigorosa de campos obrigatórios, formato de e-mail, prevenção de duplicidades e mascaramento automático de senhas (`UserData.masked_password`).
* `core/onboarding.py`: Execução do fluxo de cadastro com esperas explícitas, medição de tempo em milissegundos e captura de screenshots apenas em falhas/timeouts (`logs/screenshots/`).
* `core/executor.py`: Orquestrador concorrente (`asyncio.Semaphore`), fila de tarefas, pacing de carga (`RATE_LIMIT_DELAY`), retentativas automáticas (`MAX_RETRIES`) e captura graciosa de interrupção (SIGINT/SIGTERM).
* `core/reporter.py`: Logs rotativos de 5MB (`logs/qa_execution.log`), exportação individual em CSV (`reports/resultados.csv`) e consolidado estatístico em JSON (`reports/resumo.json`).
* `main.py`: Ponto de entrada CLI interativo.
* `tests/`: 17 testes unitários e de integração E2E com servidor mock local (`tests/mock_server.py`).

---

## 3. Resumo dos Requisitos Atendidos

1. **AdsPower Local API:** Totalmente integrada via HTTP REST, usando porta padrão `50325`, suporte a API Key opcional, reutilização de sessões ativas e desligamento de processos para não consumir RAM residual.
2. **Segurança de Credenciais:** As senhas nunca aparecem nos logs ou na tela do terminal.
3. **Massa de Dados Dinâmica:** Novos cadastros podem ser adicionados ao arquivo `data/usuarios.csv` sem alterar código.
4. **Relatórios e Estatísticas:** Cálculo em tempo de execução do **Percentil 95 (p95)**, tempo médio e taxa de sucesso percentual.
5. **Modo Híbrido:** Permite executar com AdsPower (`--use-adspower`) ou de modo 100% autônomo com Playwright local (`--local`).

---

## 4. Como Rodar em Outro Computador (Passo a Passo Rápido)

```bash
# 1. Acessar a pasta
cd teste-contas

# 2. Criar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # (ou .venv\Scripts\Activate.ps1 no Windows)

# 3. Instalar dependências
pip install -r requirements.txt
playwright install chromium

# 4. Validar os testes automatizados
pytest -v

# 5. Criar arquivo de configuração .env
cp .env.example .env

# 6. Executar o framework
# Modo Local:
python main.py --local --url http://127.0.0.1:8080/register

# Modo AdsPower:
python main.py --use-adspower --concurrency 2
```

---

## 5. Histórico de Testes Validados

* **Pytest:** 17 testes executados com 100% de aprovação (testes de parsing de CSV, mocked AdsPower REST API e E2E Playwright).
* **Teste com Servidor de Homologação Local:**
  * 4 cadastros executados com concorrência de 2 workers.
  * 100% de sucesso.
  * Tempo médio de execução: ~3.4 segundos por cadastro.
  * Percentil 95 (p95): ~4.0 segundos.
  * Relatórios e screenshots validados em disco.

