# Histórico Completo de Conversa e Desenvolvimento – QA Automation

Este documento contém o registro cronológico, detalhado e técnico de todas as etapas de desenvolvimento, decisões de engenharia, problemas encontrados e soluções implementadas no framework **QA Onboarding Automation**.

Ele serve para restaurar **100% do contexto** caso o projeto seja aberto em outro computador, por outro engenheiro de software ou por outro assistente de IA.

---

## 1. Linha do Tempo do Projeto

### Etapa 1: Definição dos Requisitos Técnicos e Arquitetura
* **Demanda:** Desenvolver um framework robusto em Python 3.11+ para testes de QA e carga no fluxo de onboarding de uma aplicação web.
* **Tecnologias Selecionadas:**
  * `Playwright`: Conexão CDP e automação de interface.
  * `AdsPower Local API`: Gestão dos perfis de navegador.
  * `HTTPX`: Cliente assíncrono para a API REST local.
  * `Rich`: Terminal profissional com barra de progresso em tempo real e tabelas.
  * `Pytest`: Validação automatizada de todos os módulos.
* **Princípio Arquitetural:** O código foi desenhado em camadas desacopladas (`config/`, `core/`, `data/`, `tests/`, `reports/`, `logs/`).

---

### Etapa 2: Implementação dos Componentes Centrais

1. **`config/settings.py`:**
   * Centralização de parâmetros usando `python-dotenv`.
   * Seletores desacoplados priorizando `data-testid`.
   * Chave de alternância `USE_ADSPOWER` (permite rodar com AdsPower ou Playwright Local).

2. **`core/adspower.py`:**
   * Cliente HTTP assíncrono para os endpoints oficiais do AdsPower:
     * `GET /status`: Health check da API local.
     * `GET /api/v1/browser/active`: Verifica se o perfil já está aberto.
     * `GET /api/v1/browser/start`: Inicia o perfil e obtém `ws.puppeteer` (WebSocket CDP).
     * `GET /api/v1/browser/stop`: Encerra o perfil após o teste.
   * **Inteligência de Parâmetros:** Identifica automaticamente se o identificador informado é numérico (passando `serial_number=X`) ou alfanumérico (passando `user_id=X`), facilitando o uso direto com a coluna `Nº` da interface do AdsPower.

3. **`core/csv_loader.py`:**
   * Leitura do arquivo `data/usuarios.csv`.
   * Validação de campos obrigatórios (`profile_id`, `email`, `password`, `name`).
   * Validação de sintaxe de e-mail e bloqueio de registros duplicados no lote.
   * **Segurança de Dados:** `UserData` implementa mascaramento estrito (`masked_password = "********"` e `repr` seguro) para impedir vazamento de senhas em logs ou terminal.

4. **`core/browser_manager.py`:**
   * Abstração unificada para o ciclo de vida da sessão:
     * No modo AdsPower: Conecta via `playwright.chromium.connect_over_cdp()`.
     * No modo Local: Inicia instâncias isoladas com `playwright.chromium.launch()`.
   * Encerramento ordenado de abas, contextos e processos remotos para evitar processos órfãos.

5. **`core/onboarding.py`:**
   * Função reutilizável `execute_onboarding()`.
   * Esperas explícitas para garantir estabilidade contra variações de rede.
   * Captura automática de screenshot apenas em falhas ou timeouts (`logs/screenshots/`).
   * Medição precisa de duração em milissegundos.

6. **`core/executor.py`:**
   * Concorrência controlada por semáforos assíncronos (`asyncio.Semaphore`).
   * Pacing entre execuções (`RATE_LIMIT_DELAY`) para planejamento de carga.
   * Retentativas com backoff exponencial para timeouts transitórios.
   * Captura de sinais do sistema (SIGINT/SIGTERM) para finalização graciosa.

7. **`core/reporter.py`:**
   * Log estruturado com `RotatingFileHandler` (limite de 5MB por arquivo).
   * Geração de `reports/resultados.csv` (detalhado) e `reports/resumo.json` (consolidado).
   * Algoritmo de cálculo do **Percentil 95 (p95)** e tempo médio.

---

### Etapa 3: Depuração e Correções Técnicas Aplicadas

Durante os primeiros testes práticos, identificamos e corrigimos dois pontos críticos:

1. **`TypeError: unhashable type: 'BrowserSession'`:**
   * **Causa:** A classe `BrowserSession` foi inicialmente definida como dataclass sem `eq=False`, impossibilitando o rastreamento seguro dentro de `set()` para evitar processos órfãos.
   * **Solução:** Aplicada a anotação `@dataclass(eq=False)` em `core/browser_manager.py`.

2. **Compatibilidade com Perfis AdsPower (`serial_number` vs `user_id`):**
   * **Causa:** Usuários muitas vezes veem apenas o número sequencial da coluna `Nº` (ex: `1`) na tela do AdsPower, e não o ID alfanumérico interno.
   * **Solução:** Implementado método `_build_profile_params` em `core/adspower.py` que detecta números e envia `serial_number`, garantindo compatibilidade total com o que o usuário enxerga na interface.

---

### Etapa 4: Validação Prática e Testes

1. **Suite de Testes Automatizados (`pytest`):**
   * Criados 17 testes automatizados cobrindo:
     * Validação do CSV e segurança de senhas (`test_csv_loader.py`).
     * Mocks da API do AdsPower, timeouts e health check (`test_adspower.py`).
     * Fluxo completo E2E em servidor web real com Playwright (`test_onboarding.py`).
   * **Resultado:** 17 passed em 100% dos testes.

2. **Execução de Homologação ao Vivo:**
   * Executado contra o servidor mock local (`tests/mock_server.py`) com concorrência de 2 workers:
     * 4 cadastros executados com 100% de sucesso.
     * Tempo médio: ~3.4 segundos.
     * Percentil 95 (p95): ~4.0 segundos.
     * Relatórios gerados e validados em disco.

---

### Etapa 5: Dúvidas Operacionais Respondidas

* **Onde fica a Local API no AdsPower (macOS)?**
  * Menu superior do Mac: `Adspower global` ➔ `Preferências...` (ou atalho `Cmd + ,`).
  * Ou canto superior direito da janela do AdsPower: clicar no avatar do usuário ➔ `Configurações` ➔ aba `Local API` ➔ ativar chave e verificar a porta `50325`.
* **Uso para criação de contas no próprio domínio:**
  * O framework está perfeitamente calibrado para cadastrar contas em formulários web do seu domínio (`ONBOARDING_URL`).
  * Para caixas postais diretas de e-mail (cPanel/Postfix), explicou-se a conveniência de APIs diretas de e-mail vs automação web.

---

### Etapa 6: Publicação no Git
* O repositório foi inicializado, documentado, commitado e enviado para o GitHub:
  * **URL:** `https://github.com/Alysontrx/qa-onboarding-automation.git`
  * **Branch:** `main`

---

## 2. Comandos Essenciais de Operação

```bash
# 1. Instalação de dependências
pip install -r requirements.txt
playwright install chromium

# 2. Executar suite de testes de validação
pytest -v

# 3. Execução no modo Playwright Local (com navegador visível)
python main.py --local --no-headless --url http://127.0.0.1:8080/register

# 4. Execução integrada ao AdsPower
python main.py --use-adspower --concurrency 2
```
