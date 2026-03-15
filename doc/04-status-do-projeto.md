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
- **Fase 3 — Validação real (concluída):** execução E2E smoke pós-deploy e rodada manual concorrente, com artefatos versionados.
- **Fase 4 — Bônus hiperautomação (concluída):** workflow no **Make** implementado para acionar API, salvar JSON no Google Drive e registrar metadados/link no Google Sheets.
- **Fase 5 — Fechamento de entrega (em andamento):** consolidação de evidências finais para apresentação, right-sizing final e checklist de segurança/segredos.

## Backlog imediato (próximas implementações)
- Formalizar política de retenção e expurgo no fluxo externo (Make -> Google Drive/Sheets), com prazos e responsáveis.
- Aplicar minimização de dados no payload persistido externamente (mascaramento/remoção de campos não essenciais).
- Definir governança de acesso (permissões, trilha de auditoria e revisão periódica) para pasta do Drive e planilha do Sheets.

## Evidências registradas
- E2E smoke pós-deploy (run `23096919987`, status: aprovado): [e2e-smoke-artifacts](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-23096919987/e2e-smoke-artifacts)
- Metadados da execução e instruções da coleta: [README da evidência](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-23096919987/README.md)
- E2E smoke concorrente (rodada local, `refinar_busca` true/false em paralelo): [e2e-smoke-artifacts concorrencia](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-local-concorrencia/e2e-smoke-artifacts)
- Metadados da rodada concorrente: [README da evidência concorrente](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-local-concorrencia/README.md)
- E2E smoke atualizado (rodada manual pós-ajuste de concorrência): [e2e-smoke-artifacts manual](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-manual-successo/e2e-smoke-artifacts)
- Metadados da rodada manual atualizada: [README da evidência manual](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-manual-successo/README.md)
- Evidências de desempenho em homologação (14/03/2026 19h): [performance-hml](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/performance-hml/2026-03-14-19h)
- Evidências da documentação interativa e autenticação: [api-docs](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/api-docs/2026-03-14-19h)
- Evidência de integração com Google Sheets: [google_sheets_evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_sheets_evidencia.png)
- Evidência de integração com Google Drive: [google_driver_evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_driver_evidencia.png)
- Evidência do fluxo no Make: [make_evidencia_workflow.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/make_evidencia_workflow.png)

## Ações em aberto
- Ajustar right-sizing de infraestrutura após coleta de métricas (memória, latência e taxa de erro), mantendo estabilidade como prioridade.
- Formalizar e implementar política de retenção/expurgo no consumo downstream (Drive/Sheets), incluindo rotina automatizada de limpeza.
- Revisar permissões e trilha de auditoria das integrações externas (Make, Google Drive e Google Sheets).
- Opcional de evolução: ampliar navegação para abas/tabelas adicionais de detalhe, se o escopo pós-desafio exigir maior cobertura funcional.

## Nota LGPD (retenção e expurgo)
- A API não utiliza banco de dados para persistência de consultas; o processamento principal ocorre em memória e a resposta é devolvida ao cliente.
- No fluxo externo de hiperautomação (Make -> Google Drive/Google Sheets), há persistência de dados/artefatos, conforme evidências desta entrega.
- Portanto, retenção e expurgo devem ser tratados no downstream (Make/Drive/Sheets), com política explícita de prazo, base legal e controle de acesso.
- As evidências em Base64 são transitórias na API, mas podem ser armazenadas externamente quando o fluxo de integração estiver habilitado.
