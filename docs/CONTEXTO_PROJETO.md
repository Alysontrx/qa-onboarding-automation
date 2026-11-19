# Contexto do Projeto, Playbook e Especificação M2M

Este documento unifica **100% do contexto técnico, arquitetura, histórico, Playbook Operacional e Contrato de Integração Sistema-a-Sistema (M2M)** do projeto **QA Onboarding Automation**, servindo de guia completo tanto para humanos quanto para outros sistemas, orquestradores e assistentes de IA.

---

## 1. Visão Geral e Propósito

* **Objetivo:** Framework profissional em Python 3.11+ para automação de onboarding, testes de carga e validação de confiabilidade de aplicações web.
* **Modo Híbrido:**
  * **AdsPower Local API:** Conexão direta via Chrome DevTools Protocol (CDP) aos perfis do AdsPower.
  * **Playwright Local:** Execução isolada em Chromium nativo, permitindo testes sem depender do AdsPower aberto.
* **Segurança:** As senhas nunca são exibidas em logs, terminal ou relatórios (mascaramento estrito com `UserData.masked_password`).
* **Confiabilidade:** Zero processos órfãos — todas as abas e instâncias do AdsPower são encerradas ao final de cada teste ou sob interrupção (SIGINT/SIGTERM).

---

## 2. Playbook Operacional (Onde um Complementa o Outro)

```
[1. Massa de Dados] ──> [2. Gestão de Navegador] ──> [3. Automação de Tela] ──> [4. Orquestração] ──> [5. Relatórios & Métricas]
   (csv_loader)             (browser_manager)              (onboarding)              (executor)                 (reporter)
        │                          │                            │                        │                           │
  Valida e mascara          Abre via AdsPower            Preenche campos e        Controla fila,             Calcula p95, gera
    credenciais              (CDP) ou Local              valida confirmação        concorrência e retries     CSV e JSON
```

### Como a Esteira se Complementa na Prática:
1. **Dados alimentam a Automação:** `csv_loader.py` bloqueia e-mails errados antes de abrir qualquer navegador, economizando memória.
2. **Concorrência protege o Servidor:** `executor.py` dosa quantos navegadores rodam juntos e dá pausas (`RATE_LIMIT_DELAY`) para o site não travar.
3. **AdsPower complementa o Playwright:** O AdsPower gerencia as impressões digitais dos perfis, enquanto o Playwright comanda as ações da tela via CDP em alta velocidade.
4. **Screenshots complementam os Logs:** Quando um cadastro falha, o log diz a mensagem de erro e a pasta `logs/screenshots/` guarda a imagem exata da tela no instante da falha para auditoria visual.
5. **Métricas complementam a Tomada de Decisão:** `reports/resumo.json` entrega o **Percentil 95 (p95)** para os desenvolvedores saberem a velocidade real do sistema sob estresse.

---

## 3. Especificação de Integração Sistema-a-Sistema (M2M Contract)

Para que outro sistema, bot, IA ou orquestrador automatizado converse com este framework:

### 3.1. Acoplamento via CLI / Subprocess
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

### 3.2. Contrato de Entrada (Input Payload - CSV)
O sistema gerador deve alimentar o arquivo `data/usuarios.csv` com o seguinte formato:
```csv
profile_id,email,password,name
1,teste001@meudominio.com,SenhaSegura123!,Usuario Teste 1
2,teste002@meudominio.com,SenhaSegura123!,Usuario Teste 2
```
* `profile_id`: Número do perfil do AdsPower (coluna `Nº`) ou ID alfanumérico.
* `email`: Endereço de e-mail a registrar.
* `password`: Senha para o cadastro.
* `name`: Nome a ser preenchido.

### 3.3. Contrato de Saída (Output Payload - JSON Consumível)
Ao terminar a execução, o outro sistema deve ler o arquivo **`reports/resumo.json`**:
```json
{
  "total_tests": 4,
  "success_count": 4,
  "failure_count": 0,
  "timeout_count": 0,
  "profile_error_count": 0,
  "connection_error_count": 0,
  "success_rate_percent": 100.0,
  "avg_duration_ms": 3478.48,
  "p95_duration_ms": 4096.18,
  "per_profile_summary": {
    "1": [
      {
        "email": "te***@meudominio.com",
        "status": "SUCCESS",
        "step": "COMPLETE",
        "duration_ms": 3435.87,
        "error_message": null
      }
    ]
  }
}
```

* **Dicionário de Status:**
  * `SUCCESS`: Cadastro concluído e validado na interface.
  * `FAILED`: Rejeitado pelo formulário da web (ex: e-mail duplicado).
  * `TIMEOUT`: Algum elemento demorou mais que o timeout configurado.
  * `PROFILE_ERROR`: Falha de inicialização do perfil no AdsPower.
  * `CONNECTION_ERROR`: Impossibilidade de conectar à API Local do AdsPower.

---

## 4. Dúvidas Operacionais e Configurações

* **Onde ativar a Local API no AdsPower:**
  * **No Windows:** No AdsPower, clique no ícone da engrenagem ⚙️ (ou clique no avatar do usuário no canto superior direito ➔ `Configurações`) ➔ aba `Local API` ➔ ativar chave seletora ➔ confirmar porta `50325`.
  * **No macOS:** Menu superior: `Adspower global` ➔ `Preferências...` ➔ aba `Local API`.
* **Identificador de Perfil:**
  * O número que aparece na coluna **`Nº`** (ex: `1`) pode ser colocado diretamente no arquivo `data/usuarios.csv`. O código detecta se é número e envia `serial_number=1` automaticamente.

---

## 5. Como Rodar no Windows (Execução Rápida em 1 Clique)

No Windows, você não precisa digitar comandos no terminal:
1. Abra o **AdsPower** e ative a Local API.
2. Dê **dois cliques** no arquivo `iniciar_windows.bat`.
3. Ele instala as dependências automaticamente e inicia a automação!

Caso prefira rodar via PowerShell/Prompt de Comando:
```bash
# 1. Clonar o repositório
git clone https://github.com/Alysontrx/qa-onboarding-automation.git
cd qa-onboarding-automation

# 2. Criar e ativar o ambiente virtual no Windows
python -m venv .venv
.venv\Scripts\activate.bat

# 3. Instalar dependências
pip install -r requirements.txt
playwright install chromium

# 4. Executar os testes ou a automação
pytest -v
python main.py --use-adspower --concurrency 2
```
