# Visão Geral da Operação SixtySix & Proxy 4G

Este repositório contém a automação de testes, QA e criação de contas para a infraestrutura da **SixtySix**.

O documento com o contexto completo de arquitetura, resoluções de bloqueios, autolimpeza do pool (Self-Healing) e o guia completo para utilização do **Proxy 4G Móvel via Celular Android (ADB)** encontra-se em:

👉 **[docs/CONTEXTO_OPERACAO_E_PROXY_4G.md](docs/CONTEXTO_OPERACAO_E_PROXY_4G.md)**

### Tópicos Abordados no Documento:
1. **Histórico e Diagnósticos:** Superação de bloqueios 403, migração de domínios Catch-All para Cloudflare Email Routing e rodízio 50/50.
2. **Guia Completo de Proxy 4G Móvel:** Configuração do Every Proxy no Android, redirecionamento via `adb forward` e comandos para rotação automática do Modo Avião a custo R$ 0.
3. **Arquitetura Self-Healing Pool:** Auto-Purge de pontes mortas/esgotadas no gateway local, Failover Universal transparente para clientes e o daemon Guardião do Pool com sincronização na VPS.
4. **Auditoria de Banco de Dados:** Análise de histórico de tokens, dias mais movimentados e expurgo de logs anteriores a 12/11/2026.
5. **Inventário de Repositórios e Produção:** Links e branches oficiais.
