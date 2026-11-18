# Contexto Geral do Projeto e Histórico de Desenvolvimento

Este documento unifica **100% do contexto técnico, arquitetura e histórico de decisões** do projeto **QA Onboarding Automation**, servindo de guia completo para desenvolvedores, analistas de QA e assistentes de IA em qualquer computador.

---

## 1. Visão Geral e Propósito

* **Objetivo:** Framework profissional em Python 3.11+ para testes de QA, carga e confiabilidade no fluxo de onboarding/registro de aplicações web.
* **Modo Híbrido:**
  * **AdsPower Local API:** Conexão direta via Chrome DevTools Protocol (CDP) aos perfis do AdsPower.
  * **Playwright Local:** Execução isolada em Chromium nativo, permitindo testes sem depender do AdsPower aberto.
* **Segurança:** As senhas nunca são exibidas em logs, terminal ou relatórios (mascaramento estrito com `UserData.masked_password`).
* **Confiabilidade:** Zero processos órfãos — todas as abas e instâncias do AdsPower são encerradas ao final de cada teste ou sob interrupção (SIGINT/SIGTERM).

---

## 2. Linha do Tempo e Decisões de Engenharia

### 2.1. Arquitetura Modular
O framework foi organizado em camadas desacopladas:
* `config/settings.py`: Centralização de parâmetros, `.env` e seletores da UI (preferência por `data-testid`).
* `core/adspower.py`: Cliente HTTP assíncrono para os endpoints oficiais do AdsPower (`/status`, `/api/v1/browser/active`, `/api/v1/browser/start`, `/api/v1/browser/stop`).
* `core/browser_manager.py`: Gerenciamento do ciclo de vida das sessões Playwright (CDP ou Local).
* `core/csv_loader.py`: Ingestão de `data/usuarios.csv`, validação rigorosa de campos obrigatórios, formato de e-mail e duplicidades.
* `core/onboarding.py`: Execução da automação com esperas explícitas, medição de tempo e screenshots apenas em falhas (`logs/screenshots/`).
* `core/executor.py`: Orquestrador concorrente (`asyncio.Semaphore`), fila de tarefas, pacing (`RATE_LIMIT_DELAY`) e retentativas automáticas (`MAX_RETRIES`).
* `core/reporter.py`: Logs rotativos de 5MB (`logs/qa_execution.log`), relatórios detalhados em CSV (`reports/resultados.csv`) e consolidado estatístico em JSON (`reports/resumo.json`).
* `main.py`: CLI interativo com interface Rich e barra de progresso em tempo real.
* `tests/`: 17 testes automatizados com `pytest` e servidor mock (`tests/mock_server.py`).

### 2.2. Depuração e Problemas Resolvidos
1. **`TypeError: unhashable type: 'BrowserSession'`:**
   * Ajustada a dataclass com `@dataclass(eq=False)` em `core/browser_manager.py`, permitindo rastrear as instâncias abertas em conjuntos (`set`) para encerramento seguro.
2. **Compatibilidade com Perfis AdsPower (`serial_number` vs `user_id`):**
   * O cliente `core/adspower.py` detecta automaticamente se o identificador informado no CSV é numérico (passando `serial_number=X`) ou alfanumérico (passando `user_id=X`), permitindo usar diretamente o número exibido na coluna **`Nº`** do AdsPower (ex: perfil `1`).

---

## 3. Dúvidas Operacionais Resolvidas

* **Onde ativar a Local API no AdsPower (macOS):**
  * No menu superior do Mac: `Adspower global` ➔ `Preferências...` (ou atalho `Cmd + ,`), aba **Local API** ➔ ativar chave seletora ➔ confirmar porta `50325`.
  * Ou no canto superior direito da janela do AdsPower: clicar no avatar do usuário ➔ `Configurações` ➔ aba `Local API`.
* **Identificador de Perfil:**
  * O número que aparece na coluna **`Nº`** (ex: `1`) pode ser colocado diretamente no arquivo `data/usuarios.csv`.
* **Criação de Contas no Próprio Domínio:**
  * O framework está pronto para preencher formulários web no domínio desejado, bastando configurar a variável `ONBOARDING_URL` no `.env`.

---

## 4. Métricas e Testes Já Validados

1. **Suite Pytest:**
   * 17 testes executados com 100% de sucesso (`tests/test_csv_loader.py`, `tests/test_adspower.py` e `tests/test_onboarding.py`).
2. **Execução E2E ao Vivo:**
   * Executado contra servidor local de teste com concorrência de 2 workers:
     * Taxa de sucesso: 100.0%
     * Tempo médio por cadastro: ~3.4 segundos.
     * Percentil 95 (p95): ~4.0 segundos.
     * Relatórios CSV e JSON gerados com sucesso.

---

## 5. Como Rodar em Outro Computador (Passo a Passo)

```bash
# 1. Clonar o repositório
git clone https://github.com/Alysontrx/qa-onboarding-automation.git
cd qa-onboarding-automation

# 2. Criar e ativar o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # (.venv\Scripts\Activate.ps1 no Windows)

# 3. Instalar dependências
pip install -r requirements.txt
playwright install chromium

# 4. Validar os testes automatizados
pytest -v

# 5. Criar arquivo .env e configurar suas variáveis
cp .env.example .env

# 6. Executar o framework:
# Modo Local (Playwright Standalone, sem AdsPower):
python main.py --local --no-headless --url http://127.0.0.1:8080/register

# Modo AdsPower (conectando na Local API):
python main.py --use-adspower --concurrency 2
```
