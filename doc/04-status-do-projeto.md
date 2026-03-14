## Status por requisito (doc/02)

- Backend Django exposto como API: **feito** (Cloud Run, deploy automático).
- Playwright/Chromium para navegação e captura: **implementado**, em uso; ainda ajustar consumo de memória.
- Evidência em Base64 na resposta: **presumido implementado** (validar no endpoint real).
- Resposta JSON com panorama + benefícios: **parcial** (testar fluxos RF-01..RF-06).
- Logs de execução/falhas: **básico** via Django/Cloud Logging; falta enriquecer mensagens do robô.
- Autenticação JWT HS256 via `API_MASTER_KEY`: **ajustado** (código e docs); falta garantir `API_MASTER_KEY` no deploy (secret).
- Parametrização por `.env` (SECRET_KEY, API_MASTER_KEY, ALLOWED_HOSTS, TTL): **feito**.
- Limite de 3 entradas por requisição e até 3 execuções paralelas: **pendente** (precisa validação e controle de carga).
- Validação de entradas (CPF/NIS/nome) e rejeição antes do navegador: **parcial** (revisar/fortalecer).
- Mensagens de erro dos cenários de teste (MOST): **pendente** validar/ajustar texto.
- Segurança/LGPD (mascarar identificadores em logs): **pendente**.

## Ações em aberto
- Garantir secret `API_MASTER_KEY` presente no GitHub Actions e redeploy.
- Testar `/api/consulta` com casos de sucesso/erro e confirmar estrutura do JSON e evidência Base64.
- Mitigar OOM: manter `--memory=2Gi`, `--concurrency=1`; revisar fechamento do Playwright; se necessário, subir para 2 CPU ou otimizar fluxo.
- Implementar limites de batch/concorrência conforme requisito (3 entradas / até 3 execuções paralelas).
- Padronizar mensagens de erro conforme cenários (MOST) e mascarar CPF/NIS em logs.
