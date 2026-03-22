## Atalhos rápidos
- Variáveis de ambiente (referência completa): [README - Referência de variáveis de ambiente](../README.md#env-reference)
- Requisitos e contrato da API: [doc/02-requisito-do-projeto.md](./02-requisito-do-projeto.md)

## Status por requisito (doc/02)

- Backend Django exposto como API: **feito** (Cloud Run, com deploy controlado: manual ou automático por tag `v*`).
- Playwright/Chromium para navegação e captura: **feito** (fluxo operacional com tratamento de navegação e extração).
- Evidência em Base64 na resposta: **feito** (panorama, ausência de benefício e detalhes quando aplicável).
- Resposta JSON com panorama + benefícios: **feito** para o escopo principal; detalhes completos dependem da estrutura disponível em cada tela do portal.
- Logs de execução/falhas: **feito** com eventos estruturados, correlação por `id_consulta` e rastreio de `etapa_falha` via Django/Cloud Logging e logs do robô.
- Observabilidade de métricas (RF-12): **feito em ambiente local** com endpoint `/metrics`, coleta Prometheus e dashboard Grafana.
- Notificação de alerta (RF-13): **feito em ambiente local** com regra no Grafana enviando alerta para Telegram.
- Escopo de observabilidade em cloud: **não aplicado nesta fase** por decisão de custo/benefício no contexto de desafio; stack validada localmente.
- Autenticação JWT HS256 via `API_MASTER_KEY`: **feito** (endpoint de token + validação Bearer na consulta, com token de uso único por requisição).
- Parametrização por `.env` (SECRET_KEY, API_MASTER_KEY, ALLOWED_HOSTS, `API_TOKEN_TTL` de segurança): **feito**.
- Integração contínua com GitHub Actions: **feito** (workflows versionados para validação/smoke).
- Entrega contínua controlada: **feito** (deploy no Cloud Run apenas manual ou por tag de versão `v*`; sem auto deploy em commit/merge de branch).
- Lote com fila interna: **feito**. Quando excede a capacidade paralela, os blocos aguardam em fila e seguem processando.
- Execução simultânea de bots (requisito do desafio): **feito no código** (API e runner async), com browser fixo em `1` e paralelismo por abas ajustável via `BOT_MAX_CONSULTAS_POR_BROWSER` (padrão `1x4`).
- Flag de resposta leve sem Base64: **feito** (`incluir_base64=false` por request; default configurável por `BOT_INCLUDE_BASE64_DEFAULT`).
- Concorrência de requisições HTTP por instância: **configurável** via `GUNICORN_WORKERS` e `GUNICORN_THREADS` (padrão `1x2`, ou seja, até 2 requisições simultâneas por instância).
- Validação de entradas (CPF/NIS/nome) e rejeição antes do navegador: **feito**.
- Mensagens de retorno dos cenários de teste (MOST): **feito** para os cenários principais (incluindo `status="not_found"` em CPF/NIS inexistente e nome sem resultado).
- Segurança/LGPD: **feito** com mascaramento de identificadores nos logs, autenticação por token e uso de segredos via variáveis de ambiente.
- E2E smoke em ambiente real (API online): **feito** (`tests/test_e2e_smoke.py` + workflow `.github/workflows/e2e-smoke.yml` com artefatos, emissão de token dedicada por chamada concorrente).

## Linha do tempo (execução)
- **Fase 1 — Fundação do bot (11/03 a 12/03/2026, concluída):** criação da base Playwright, modularização inicial (`navigation`/`extraction`) e estruturação da documentação técnica.
- **Fase 2 — API e segurança (12/03 a 13/03/2026, concluída):** API Django/DRF, autenticação JWT no fluxo OAuth2 `client_credentials`, validações de entrada e padronização inicial do contrato.
- **Fase 3 — Deploy e operação em cloud (14/03/2026, concluída):** pipeline de deploy no Cloud Run, ajustes de recursos/execução e política de disparo controlada (manual ou automática por tag `v*`).
- **Fase 4 — Qualidade de contrato e evidências (14/03 a 15/03/2026, concluída):** padronização de respostas/erros, testes unitários/API, E2E smoke com artefatos e campos de auditoria (`id_consulta`, `data_hora_consulta`).
- **Fase 5 — Robustez de navegação e regras de busca (15/03/2026, concluída):** melhorias de estabilidade em busca simples/refinada, score de nome, stealth e logs estruturados.
- **Fase 6 — Concorrência e performance (19/03 a 21/03/2026, concluída):** ajustes de paralelismo, infraestrutura de stress test com limites de recurso e validação de comportamento sob carga.
- **Fase 7 — Observabilidade + migração async (22/03/2026, concluída):** métricas Prometheus, dashboards/alertas Grafana (Telegram), migração para bot assíncrono como motor principal, token de uso único e consolidação documental.

## Estimativa de esforço (baseada em commits)
- Base de cálculo: histórico Git do autor principal (`José Carlos Leite`), com `134` commits entre **11/03/2026** e **22/03/2026**.
- Método usado: agrupamento por sessões de trabalho (intervalo entre commits), com cenários conservador e realista para evitar subestimação.
- Faixa estimada: **20 a 26 horas** de execução efetiva.
- Estimativa de referência para reporte: **24 horas**.
- Observação: a estimativa por commits não captura integralmente atividades sem commit imediato (planejamento, validação manual, investigação e ajustes operacionais externos).

## Backlog imediato (próximas implementações)
- Implementar store compartilhado Redis para controle global de reuso de token JWT (`jti`) em multi-worker/multi-instância.
- Implementar camada adicional de mitigação de bloqueio/CAPTCHA/WAF (controle de ritmo, redução de assinatura de automação e telemetria específica de bloqueio).
- Ampliar extração de detalhes para navegação em abas/tabelas adicionais de parcelas quando o layout exigir.
- Expandir cobertura de layouts de benefícios fora do recorte principal, mantendo fallback seguro de panorama/dados base.
- Consolidar observabilidade operacional (métricas agregadas, SLO de sucesso/latência e alerta automático).
- Finalizar right-sizing com base em métricas reais de memória, latência, taxa de erro e custo.
- Formalizar LGPD no downstream (Make -> Drive/Sheets): retenção/expurgo, minimização de dados e governança de acesso com revisão periódica.

## Evidências registradas
- E2E smoke pós-deploy (run `23096919987`, status: aprovado): [e2e-smoke-artifacts](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-23096919987/e2e-smoke-artifacts)
- Metadados da execução e instruções da coleta: [README da evidência](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-23096919987/README.md)
- E2E smoke concorrente (rodada local, `refinar_busca` true/false em paralelo): [e2e-smoke-artifacts concorrencia](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-local-concorrencia/e2e-smoke-artifacts)
- Metadados da rodada concorrente: [README da evidência concorrente](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-local-concorrencia/README.md)
- E2E smoke atualizado (rodada manual pós-ajuste de concorrência): [e2e-smoke-artifacts manual](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-manual-successo/e2e-smoke-artifacts)
- Metadados da rodada manual atualizada: [README da evidência manual](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-manual-successo/README.md)
- Evidências de desempenho em homologação (14/03/2026 19h): [performance-hml](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/performance-hml/2026-03-14-19h)
- Evidências da documentação interativa e autenticação: [api-docs](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/api-docs/2026-03-14-19h)
- Benchmarks de concorrencia (22/03/2026): [doc/05-parametros-do-teste-de-estresse.md](./05-parametros-do-teste-de-estresse.md)
- Evidência de integração com Google Sheets: [google_sheets_evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_sheets_evidencia.png)
- Evidência de integração com Google Drive: [google_driver_evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_driver_evidencia.png)
- Evidência do fluxo no Make: [make_evidencia_workflow.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/make_evidencia_workflow.png)

## Nota LGPD (retenção e expurgo)
- A API não utiliza banco de dados para persistência de consultas; o processamento principal ocorre em memória e a resposta é devolvida ao cliente.
- No fluxo externo de hiperautomação (Make -> Google Drive/Google Sheets), há persistência de dados/artefatos, conforme evidências desta entrega.
- Portanto, retenção e expurgo devem ser tratados no downstream (Make/Drive/Sheets), com política explícita de prazo, base legal e controle de acesso.
- As evidências em Base64 são transitórias na API, mas podem ser armazenadas externamente quando o fluxo de integração estiver habilitado.
