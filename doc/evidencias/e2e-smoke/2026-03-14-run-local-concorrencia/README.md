# Evidencia E2E Smoke - Rodada local com concorrencia

Origem:
- Execucao manual local em 14/03/2026
- Contexto: validacao de chamadas concorrentes (`refinar_busca=false` e `refinar_busca=true`)

Conteudo desta pasta:
- `e2e-smoke-artifacts/01_token.json`
- `e2e-smoke-artifacts/02_consulta_refinar_false.json`
- `e2e-smoke-artifacts/03_consulta_refinar_true.json`
- `e2e-smoke-artifacts/04_resumo_concorrencia.json`
- `e2e-smoke-artifacts/junit.xml`
- `e2e-smoke-artifacts.zip`

Nota de versao:
- Esta evidencia e historica (14/03/2026), anterior ao ajuste de token de uso unico por chamada concorrente.
- No estado atual do teste E2E, o artefato equivalente e `01_tokens.json`.

Objetivo:
- Demonstrar prova objetiva de execucao concorrente no E2E smoke.
