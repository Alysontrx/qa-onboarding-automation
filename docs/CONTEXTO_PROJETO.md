# Contexto do Projeto e Playbook Operacional

Este documento unifica **100% do contexto técnico, arquitetura, histórico e o Playbook Operacional** do projeto **QA Onboarding Automation**, servindo de guia completo para desenvolvedores, analistas de QA e assistentes de IA em qualquer computador.

---

## 1. Visão Geral e Propósito

* **Objetivo:** Framework profissional em Python 3.11+ para testes de QA, carga e confiabilidade no fluxo de onboarding/registro de aplicações web.
* **Modo Híbrido:**
  * **AdsPower Local API:** Conexão direta via Chrome DevTools Protocol (CDP) aos perfis do AdsPower.
  * **Playwright Local:** Execução isolada em Chromium nativo, permitindo testes sem depender do AdsPower aberto.
* **Segurança:** As senhas nunca são exibidas em logs, terminal ou relatórios (mascaramento estrito com `UserData.masked_password`).
* **Confiabilidade:** Zero processos órfãos — todas as abas e instâncias do AdsPower são encerradas ao final de cada teste ou sob interrupção (SIGINT/SIGTERM).

---

## 2. Playbook Operacional (Onde um Complementa o Outro)

O framework funciona como uma esteira contínua, onde o resultado de cada módulo é o insumo indispensável para o próximo:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   ARQUITETURA COMPLEMENTAR                                     │
├────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                │
│   ETAPA 1: csv_loader.py (A Base dos Dados)                                                    │
│   └── Lê data/usuarios.csv, sanitiza os e-mails, valida duplicidades e mascara senhas.         │
│       │                                                                                        │
│       ▼ Entrega lista de UserData tipados e validados                                          │
│                                                                                                │
│   ETAPA 2: executor.py (O Maestro da Concorrência)                                             │
│   └── Pega a lista do CSV, enfileira tarefas e gerencia o semáforo de concorrência.            │
│       │                                                                                        │
│       ▼ Para cada usuário, solicita uma sessão isolada                                         │
│                                                                                                │
│   ETAPA 3: browser_manager.py & adspower.py (A Infraestrutura de Navegação)                    │
│   └── No modo AdsPower: chama a API local, abre o perfil (ex: nº 1) e extrai o WebSocket.      │
│   └── No modo Local: lança Chromium nativo do Playwright para testes rápidos.                  │
│       │                                                                                        │
│       ▼ Entrega uma instância de Page ativa e conectada                                        │
│                                                                                                │
│   ETAPA 4: onboarding.py (A Execução na Interface Web)                                         │
│   └── Acessa a URL do seu domínio, preenche nome/email/senha, submete e afere o resultado.     │
│   └── Se houver erro ou timeout, tira print de auditoria e fecha a aba.                        │
│       │                                                                                        │
│       ▼ Retorna ExecutionResult com status (SUCCESS, FAILED, TIMEOUT) e tempo em ms            │
│                                                                                                │
│   ETAPA 5: reporter.py (A Inteligência Estatística de QA)                                      │
│   └── Registra no log rotativo, calcula o percentil 95 (p95) e grava resultados.csv e resumo. │
│                                                                                                │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Como a Esteira se Complementa na Prática:
1. **Dados alimentam a Automação:** `csv_loader.py` bloqueia e-mails errados antes de abrir qualquer navegador, economizando memória.
2. **Concorrência protege o Servidor:** `executor.py` dosa quantos navegadores rodam juntos e dá pausas (`RATE_LIMIT_DELAY`) para o site não travar.
3. **AdsPower complementa o Playwright:** O AdsPower gerencia as impressões digitais dos perfis, enquanto o Playwright comanda as ações da tela via CDP em alta velocidade.
4. **Screenshots complementam os Logs:** Quando um cadastro falha, o log diz a mensagem de erro e a pasta `logs/screenshots/` guarda a imagem exata da tela no instante da falha para auditoria visual.
5. **Métricas complementam a Tomada de Decisão:** `reports/resumo.json` entrega o **Percentil 95 (p95)** para os desenvolvedores saberem a velocidade real do sistema sob estresse.

---

## 3. Matriz de Trabalho em Equipe (Divisão de Papéis)

| Papel | Responsabilidade Principal | Arquivos Envolvidos |
| :--- | :--- | :--- |
| **Operador de Dados / QA** | Define a lista de e-mails, domínios e senhas a testar | `data/usuarios.csv` |
| **Engenheiro de Automação** | Ajusta seletores dos botões e campos se o site mudar | `config/settings.py`, `core/onboarding.py` |
| **Operador de Infraestrutura** | Abre os perfis do AdsPower e configura portas de API | `.env`, AdsPower Local API |
| **Líder Técnico / Gestor** | Analisa o relatório consolidado de métricas e p95 | `reports/resumo.json`, `reports/resultados.csv` |

---

## 4. Dúvidas Operacionais e Configurações

* **Onde ativar a Local API no AdsPower (macOS):**
  * Menu superior do Mac: `Adspower global` ➔ `Preferências...` (ou atalho `Cmd + ,`), aba **Local API** ➔ ativar chave seletora ➔ confirmar porta `50325`.
  * Ou no canto superior direito da janela do AdsPower: clicar no avatar do usuário ➔ `Configurações` ➔ aba `Local API`.
* **Identificador de Perfil:**
  * O número que aparece na coluna **`Nº`** (ex: `1`) pode ser colocado diretamente no arquivo `data/usuarios.csv`. O código detecta se é número e envia `serial_number=1` automaticamente.
* **Criação de Contas no Próprio Domínio:**
  * Basta configurar a variável `ONBOARDING_URL` no `.env` apontando para o link de cadastro do seu domínio.

---

## 5. Como Rodar em Qualquer Computador

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
