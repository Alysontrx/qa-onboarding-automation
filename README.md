# Framework de QA – Automação de Onboarding com AdsPower + Playwright

Framework profissional e escalável de automação de testes de qualidade (QA) projetado para validar a resiliência, escalabilidade e performance do fluxo de onboarding/registro de aplicações web.

O framework suporta execução híbrida:
1. **Modo AdsPower**: Integração direta com a **AdsPower Local API** para automação de perfis específicos via Chrome DevTools Protocol (CDP) com o Playwright.
2. **Modo Local**: Execução em instâncias isoladas de Chromium via Playwright, ideal para desenvolvimento local, testes unitários e esteiras de CI/CD sem dependência do AdsPower.

---

## 1. Arquitetura do Projeto

```text
teste-contas/ (ou qa-onboarding/)
│
├── config/
│   ├── __init__.py
│   └── settings.py          # Configurações centralizadas, tipadas e .env
│
├── data/
│   └── usuarios.csv         # Massa de dados de teste (profile_id, email, password, name)
│
├── core/
│   ├── __init__.py
│   ├── adspower.py          # Cliente HTTP assíncrono para AdsPower Local API
│   ├── browser_manager.py   # Gerenciador de ciclo de vida das sessões CDP / Playwright
│   ├── onboarding.py        # Automação do formulário com esperas explícitas
│   ├── csv_loader.py        # Leitura, higienização, validação e mascaramento de senhas
│   ├── executor.py          # Orquestrador concorrente, retentativas e rate-limiting
│   └── reporter.py          # Logging rotativo, cálculo de p95 e geração de CSV/JSON
│
├── logs/
│   ├── qa_execution.log     # Log rotativo estruturado
│   └── screenshots/         # Capturas de tela automáticas apenas em falhas
│
├── reports/
│   ├── resultados.csv       # Relatório individualizado de cada execução
│   └── resumo.json          # Sumário com métricas (taxa de sucesso, média, p95)
│
├── tests/
│   ├── __init__.py
│   ├── test_csv_loader.py   # Testes unitários de validação e sanitização de dados
│   ├── test_adspower.py     # Testes de integração e mock da AdsPower Local API
│   ├── test_onboarding.py   # Testes E2E com servidor HTTP real e Playwright
│   └── mock_server.py       # Servidor HTTP local para homologação e testes offline
│
├── main.py                  # Ponto de entrada com CLI interativo e barra de progresso
├── requirements.txt         # Dependências do projeto
├── pytest.ini               # Configuração do pytest e pytest-asyncio
├── .env.example             # Modelo de variáveis de ambiente
├── .gitignore
└── README.md
```

---

## 2. Tecnologias Utilizadas

- **Python 3.11+** (compatível com 3.11, 3.12 e 3.13)
- **Playwright (Async API)**: Conexão CDP e automação confiável de interface.
- **HTTPX**: Cliente HTTP assíncrono de alta performance para a Local API do AdsPower.
- **Rich**: Interface de terminal profissional com barras de progresso e tabelas em tempo real.
- **Pytest & Pytest-Asyncio**: Suite completa de testes unitários e de integração.
- **Python-Dotenv**: Carregamento transparente de variáveis de configuração.

---

## 3. Instalação e Preparação do Ambiente

### 3.1. Clonar ou Acessar o Diretório
```bash
cd "/home/alysontrx/Área de trabalho/teste-contas"
```

### 3.2. Criar e Ativar Ambiente Virtual
Utilizando `uv` (recomendado) ou `venv` padrão:
```bash
# Com uv:
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
playwright install chromium

# Ou com python3 venv convencional:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

---

## 4. Configuração de Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env`:
```bash
cp .env.example .env
```

Parâmetros disponíveis no `.env`:

| Variável | Padrão | Descrição |
| :--- | :--- | :--- |
| `ADSPOWER_URL` | `http://127.0.0.1:50325` | Endereço da Local API do AdsPower |
| `ADSPOWER_API_KEY` | *(vazio)* | Chave de API configurada no AdsPower (se aplicável) |
| `USE_ADSPOWER` | `false` | `true` para usar AdsPower ou `false` para Playwright local |
| `ONBOARDING_URL` | `http://localhost:3000/register` | URL da tela de cadastro de homologação |
| `MAX_CONCURRENCY` | `2` | Número máximo de navegadores executando simultaneamente |
| `DEFAULT_TIMEOUT` | `10000` | Timeout por etapa em milissegundos |
| `MAX_RETRIES` | `2` | Tentativas extras em caso de timeout transitório |
| `RATE_LIMIT_DELAY` | `1.0` | Intervalo em segundos entre o início de novos cadastros |
| `HEADLESS` | `true` | Se `true`, roda os navegadores locais sem abrir janela |
| `CSV_PATH` | `data/usuarios.csv` | Caminho do arquivo de massa de dados |

---

## 5. Como Configurar a Integração com AdsPower

1. No aplicativo do **AdsPower**, vá em **Configurações / Local API**.
2. Certifique-se de que a API local está **habilitada** e anote a porta (por padrão `50325`).
3. Obtenha os **User IDs** dos perfis que deseja testar (ex: `perfil_001`, `j1k2l3...`).
4. Cadastre esses IDs na primeira coluna (`profile_id`) do seu arquivo `data/usuarios.csv`.
5. No arquivo `.env`, defina:
   ```env
   USE_ADSPOWER=true
   ADSPOWER_URL=http://127.0.0.1:50325
   ```
6. O framework conecta automaticamente na porta da API, solicita a abertura do navegador, recupera o `ws.puppeteer` (WebSocket CDP) e assume o controle via Playwright. Ao finalizar, o framework fecha o perfil no AdsPower para evitar processos órfãos.

---

## 6. Estrutura do Arquivo CSV de Entrada (`data/usuarios.csv`)

O arquivo deve conter os seguintes cabeçalhos obrigatórios:

```csv
profile_id,email,password,name
perfil_001,qa001@exemplo.com,SenhaSegura123!,Ana QA
perfil_002,qa002@exemplo.com,SenhaSegura123!,Carlos QA
perfil_003,qa003@exemplo.com,SenhaSegura123!,Mariana QA
perfil_004,qa004@exemplo.com,SenhaSegura123!,Rodrigo QA
```

### Regras de Validação:
- Todas as 4 colunas são obrigatórias em todas as linhas.
- Validação estrita do formato de e-mail.
- Detecção e bloqueio de `profile_id` ou `email` duplicados dentro do mesmo lote.
- **Segurança**: Senhas são mascaradas em memória (`UserData.masked_password`) e **nunca** são salvas nos logs nem nos relatórios.

---

## 7. Como Executar

### 7.1. Execução de Testes Unitários e E2E (Pytest)
```bash
.venv/bin/pytest -v
```
Todos os 17 testes validam o carregador CSV, o cliente AdsPower (start, stop, active, fallback), o executor de onboarding e a geração de métricas estatísticas (p95).

### 7.2. Validação Rápida de Configurações (Dry-Run)
Verifica o CSV e configurações sem abrir navegadores:
```bash
.venv/bin/python main.py --dry-run
```

### 7.3. Teste com o Servidor Local de Homologação (Offline)
Para testar o fluxo completo de ponta a ponta sem precisar de um backend externo:

1. Inicie o servidor mock de teste:
   ```bash
   .venv/bin/python tests/mock_server.py 8080
   ```
2. Em outro terminal, execute o framework apontando para ele:
   ```bash
   .venv/bin/python main.py --url http://127.0.0.1:8080/register
   ```

### 7.4. Execução em Produção / Homologação
```bash
# Execução padrão (conforme variáveis do .env):
.venv/bin/python main.py

# Forçando modo AdsPower com 4 perfis simultâneos:
.venv/bin/python main.py --use-adspower --concurrency 4

# Forçando modo Playwright Local com navegadores visíveis (debug visual):
.venv/bin/python main.py --local --no-headless
```

---

## 8. Relatórios e Métricas de Confiabilidade

Ao término da esteira, o framework gera automaticamente:

1. **`reports/resultados.csv`**:
   - Registro linha a linha de cada teste com timestamp, profile_id, e-mail mascarado, status, etapa final, duração em milissegundos, mensagem de erro e caminho da captura de tela (se houver).
2. **`reports/resumo.json`**:
   - Consolidado estatístico:
     - Total de testes
     - Contadores de `SUCCESS`, `FAILED`, `TIMEOUT`, `PROFILE_ERROR`, `CONNECTION_ERROR`
     - Taxa de sucesso percentual
     - Tempo médio de execução (`avg_duration_ms`)
     - Percentil 95 (`p95_duration_ms`)
     - Detalhamento por perfil
3. **`logs/qa_execution.log`**:
   - Log estruturado com rotação automática de 5MB (mantém até 5 arquivos históricos).
4. **`logs/screenshots/`**:
   - Screenshots gerados automaticamente em caso de falha ou timeout, nomeados com perfil e timestamp.

---

## 9. Seletores Customizáveis da Aplicação

Caso a sua aplicação web utilize seletores específicos, edite a classe `SelectorsConfig` em `config/settings.py`:

```python
class SelectorsConfig:
    email: str = "[data-testid='input-email'], input[type='email']"
    password: str = "[data-testid='input-password'], input[type='password']"
    name: str = "[data-testid='input-name'], input[name='name']"
    submit: str = "[data-testid='btn-submit'], button[type='submit']"
    success_message: str = "[data-testid='success-message'], .success-msg"
    error_message: str = "[data-testid='error-message'], .error-msg"
```
Recomenda-se utilizar atributos `data-testid` para máxima resiliência e estabilidade contra alterações de layout.

