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

## Ações em aberto
- Consolidar validação em ambiente homologação com chamadas reais ao portal para registrar evidências finais de RF-01 a RF-06.
- Executar e registrar evidência de teste de execução simultânea (2-3 consultas em paralelo) para apresentação técnica.
- Ajustar right-sizing de infraestrutura após coleta de métricas (memória, latência e taxa de erro), mantendo estabilidade como prioridade.
- Definir política de retenção/expurgo para evidências em Base64 no consumo downstream (governança LGPD).
- Opcional de evolução: ampliar navegação para abas/tabelas adicionais de detalhe, se o escopo pós-desafio exigir maior cobertura funcional.
