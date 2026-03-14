## Status por requisito (doc/02)

- Backend Django exposto como API: **feito** (Cloud Run, deploy automático).
- Playwright/Chromium para navegação e captura: **feito** (fluxo operacional com tratamento de navegação e extração).
- Evidência em Base64 na resposta: **feito** (panorama, ausência de benefício e detalhes quando aplicável).
- Resposta JSON com panorama + benefícios: **feito** para o escopo principal; detalhes completos dependem da estrutura disponível em cada tela do portal.
- Logs de execução/falhas: **feito (nível básico)** via Django/Cloud Logging e logs do robô.
- Autenticação JWT HS256 via `API_MASTER_KEY`: **feito** (endpoint de token + validação Bearer na consulta).
- Parametrização por `.env` (SECRET_KEY, API_MASTER_KEY, ALLOWED_HOSTS, TTL): **feito**.
- Limite de 3 entradas por requisição: **feito**. Execução paralela da API está **intencionalmente limitada** por configuração de runtime para estabilidade.
- Execução simultânea de bots (requisito do desafio): **feito no código** (runner local e batch); em produção, paralelismo está ajustado de forma conservadora para estabilidade.
- Validação de entradas (CPF/NIS/nome) e rejeição antes do navegador: **feito**.
- Mensagens de erro dos cenários de teste (MOST): **feito** para os cenários principais (CPF/NIS inexistente e nome sem resultado).
- Segurança/LGPD (mascarar identificadores em logs): **feito (básico)**.
- E2E smoke em ambiente real (API online): **feito** (`tests/test_e2e_smoke.py` + workflow `.github/workflows/e2e-smoke.yml` com artefatos).

## Linha do tempo (execução)
- **Fase 1 — Base técnica (concluída):** bot Playwright, API Django, autenticação, deploy Cloud Run, documentação Swagger.
- **Fase 2 — Robustez e contrato (concluída):** padronização de erros/respostas, cobertura de testes unitários/API, documentação de payload e formato de retorno.
- **Fase 3 — Validação real (em andamento):** execução E2E smoke pós-deploy, coleta de evidências dos cenários RF-01..RF-06 e validação de estabilidade.
- **Fase 4 — Bônus hiperautomação (próxima):** workflow para acionar API, salvar JSON no Google Drive e registrar metadados/link no Google Sheets.
- **Fase 5 — Fechamento de entrega (próxima):** evidências finais para apresentação, right-sizing final e checklist de segurança/segredos.

## Backlog imediato (próximas implementações)
- Implementar Parte 2 (bônus):
  - Chamar `/api/token/` e `/api/consulta/` no orquestrador (Activepieces/Make/Zapier).
  - Salvar JSON no Google Drive no padrão `[IDENTIFICADOR_UNICO]_[DATA_HORA].json`.
  - Atualizar linha no Google Sheets com identificador, nome, CPF (mascarado), data/hora e link do arquivo.
- Incluir evidência no repositório/documentação da execução simultânea (2-3 consultas).
- Consolidar política de retenção/expurgo para evidências em Base64.

## Evidências registradas
- E2E smoke pós-deploy (run `23096919987`, status: aprovado): [e2e-smoke-artifacts](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-23096919987/e2e-smoke-artifacts)
- Metadados da execução e instruções da coleta: [README da evidência](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-23096919987/README.md)
- Evidências de desempenho em homologação (14/03/2026 19h): [performance-hml](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/performance-hml/2026-03-14-19h)
- Evidências da documentação interativa e autenticação: [api-docs](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/api-docs/2026-03-14-19h)

## Ações em aberto
- Consolidar validação em ambiente homologação com chamadas reais ao portal para registrar evidências finais de RF-01 a RF-06.
- Executar e registrar evidência de teste de execução simultânea (2-3 consultas em paralelo) para apresentação técnica.
- Ajustar right-sizing de infraestrutura após coleta de métricas (memória, latência e taxa de erro), mantendo estabilidade como prioridade.
- Definir política de retenção/expurgo para evidências em Base64 no consumo downstream (governança LGPD).
- Opcional de evolução: ampliar navegação para abas/tabelas adicionais de detalhe, se o escopo pós-desafio exigir maior cobertura funcional.
