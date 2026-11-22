# Contexto Técnico da Operação SixtySix, Infraestrutura e Proxy 4G Móvel

Este documento consolida todo o histórico, diagnósticos, arquitetura implementada e especificações técnicas da infraestrutura da **SixtySix**, incluindo o plano e configuração do **Proxy 4G Móvel com Rotação via ADB**.

---

## 1. Histórico e Diagnóstico Inicial de Gargalos

### 1.1. Bloqueio HTTP 403 `signup_blocked`
* **Causa Raiz:** O domínio antigo `@sixtysix.online` recebeu 1.289 tentativas de cadastro em um intervalo de 48h. Isso disparou uma regra severa de blacklist no Castle.io (sistema antifraude da Lovable). Mesmo quando o Cloudflare Turnstile resolvia com sucesso, o backend recusava imediatamente com `"Registration denied due to suspicious activity"`.
* **Solução:** Migração completa para Cloudflare Email Routing com Catch-All em novos domínios virgens:
  * `emporioburguers.shop` (Cloudflare NS `gannon` / `mona`)
  * `destravacreditoquiz.com.br` (Cloudflare NS `zara` / `dakota`)
  * Encaminhamento direto para a conta-mãe: `alissonmedeiroz007@gmail.com`.
* **Rodízio 50/50:** Implementado no gerador (`proton_inbox_api.py`) alternância automática entre os domínios a cada conta, dividindo a volumetria e eliminando o risco de reputação negativa.

### 1.2. Proteção de Banda do Proxy Residencial (AllanProxys)
* Para evitar queima de créditos em nós lentos:
  * Trava de segurança de **21 segundos** no Turnstile nativo.
  * Máximo de 2 tentativas por erro antes do failover.
  * Circuit Breaker que aborta o lote se houverem 2 falhas consecutivas de rede.

---

## 2. Arquitetura do Proxy 4G Móvel (Custo Zero e Rotação Infinita)

O uso de proxies móveis 4G via celular Android conectado ao computador substitui a compra de proxies residenciais pagos por GB. As conexões de operadoras de telefonia móvel (Claro, Vivo, TIM) utilizam CGNAT em redes celulares, o que confere a mais alta reputação IP perante Cloudflare Turnstile e Castle.io.

### 2.1. Como Funciona a Rotação de IP
1. Cada vez que o **Modo Avião** é ativado e desativado no celular por 3 a 5 segundos, a torre da operadora desconecta a sessão e aloca um **IP público 100% novo e limpo**.
2. O tráfego de dados passa diretamente pelo plano de dados móveis do chip, resultando em custo **R$ 0 por gigabyte** de proxy.

### 2.2. Componentes Necessários
1. **Smartphone Android com chip 4G/5G** com dados ativos.
2. **Cabo USB de boa qualidade** conectado ao PC.
3. **App Proxy no Android:**
   * Recomendado: **Every Proxy** (gratuito na Play Store).
   * No app, basta ativar o toggle **HTTP** (porta padrão: `8080`).
4. **Depuração USB (ADB):**
   * Ativada em *Configurações > Opções do Desenvolvedor > Depuração USB*.
   * Permite que o PC alterne o Modo Avião via script sem necessidade de intervenção física.

### 2.3. Roteamento e Comandos de Automação (ADB)
No computador, o redirecionamento de porta é feito via ADB:
```bash
# Redireciona a porta 8080 do celular para o localhost do PC
adb forward tcp:8080 tcp:8080
```
Com isso, o script de automação aponta o proxy para:
`http://127.0.0.1:8080` (sem necessidade de usuário e senha).

Para alternar o IP automaticamente entre contas:
```bash
# Liga o modo avião
adb shell cmd connectivity airplane-mode enable

# Aguarda 3 segundos
timeout /t 3 /nobreak >nul

# Desliga o modo avião para pegar novo IP da torre
adb shell cmd connectivity airplane-mode disable

# Aguarda a reconexão da rede 4G
timeout /t 4 /nobreak >nul
```

---

## 3. Arquitetura Self-Healing Pool (Autolimpeza e Alta Disponibilidade)

Para manter o cluster de inteligência artificial 100% disponível para os clientes da SixtySix, foram implementados três pilares de auto-recuperação:

### 3.1. Auto-Purge de Pontes Esgotadas (`desktop-local-server.ts`)
* Quando uma ponte atinge o limite de créditos (HTTP 402) ou tem seu projeto arquivado/removido (HTTP 404/502), o gateway executa a função `purgeBridge()`:
  * Remove a URL morta imediatamente do arquivo `bridges.txt` em disco.
  * Remove da memória do processo em tempo real.

### 3.2. Failover Universal Transparente
* O gateway não devolve erro para o cliente se apenas uma ponte falhar.
* Se a ponte atual retornar qualquer código de erro (`401, 402, 404, 500, 502, 503` ou falha de conexão/timeout):
  1. A ponte é purgada automaticamente.
  2. O gateway pula instantaneamente para a próxima ponte ativa do pool.
  3. Realiza até 6 tentativas transparentes antes de gerar qualquer erro ao cliente.

### 3.3. Guardião do Pool (`guardiao_pool.py`)
* Daemon em background que monitora o estoque de pontes no `bridges.txt`.
* Se o número de pontes ativas cair abaixo do limiar de segurança (ex: 20 pontes), o Guardião:
  1. Dispara o gerador headless para criar novos lotes de contas.
  2. Realiza o remix e deploy automático das novas pontes.
  3. Adiciona as URLs ao topo do `bridges.txt`.
  4. Sincroniza via SCP diretamente com a VPS de produção (`216.22.31.223`).

---

## 4. Auditoria de Métricas e Dados Históricos (Supabase `gateway_usage`)

Auditoria realizada no banco de dados da SixtySix com filtro exclusivo em chamadas bem-sucedidas (HTTP 200):

* **Expurgo de Logs Antigos:** O script de migração [`supabase/limpeza-logs-api-antiga.sql`](file:///c:/Users/Alysson/sixtyosix/supabase/limpeza-logs-api-antiga.sql) expurgou todos os registros anteriores a `12/11/2026 02:25 BRT` (`05:25 UTC`). Os dias 10 e 11 não constam no banco por terem pertencido à API legada.
* **Dia 12/11 (Estreia da Nova API):** Registrou 927 Milhões de tokens e 4.352 requisições 200, com 1.111 erros 503 e instabilidade natural de rollout.
* **Dia Recorde de Acertos (10 a 15 de Novembro):**
  * **Data:** **14 de Novembro de 2026**
  * **Volume Real de Acertos:** **6.114,69 Milhões de Tokens (6,11 Bilhões)**
  * **Requisições HTTP 200:** **29.820 chamadas** atendendo 19 clientes simultâneos.
  * **Modelos Mais Consumidos:** `claude-fable-5.2` (4,64 Bi) e `claude-opus-5.5` (1,45 Bi).
* **Total Acumulado Histórico (200 OK):** Mais de **35 Bilhões de tokens** processados.

---

## 5. Repositórios e Endpoints de Produção

* **Aplicação Principal:** `https://github.com/AssnzMoney/sixtyosix` (branch: `main`)
* **Site & Gateway de Produção:** `https://github.com/AssnzMoney/sixtyosix.git` (branch: `codex/current-six-review-20261118`)
* **Automação QA:** `https://github.com/Alysontrx/qa-onboarding-automation` (branch: `main`)
* **VPS Produção:** IP `216.22.31.223` (caminho: `/home/sixtysix/app/integrations/lovable-test/bridges.txt`)
* **Endpoint de Telemetria ao Vivo:** `https://www.sixtysix.online/api/pool-status`
