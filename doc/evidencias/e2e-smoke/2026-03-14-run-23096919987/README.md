# Evidencia E2E Smoke - Run 23096919987

Coloque aqui os artefatos baixados do GitHub Actions (workflow `E2E Smoke Tests`).

Arquivos esperados:
- `01_token.json`
- `02_consulta_refinar_false.json`
- `03_consulta_refinar_true.json`
- `junit.xml`

Nota de versao:
- Este pacote e historico (14/03/2026), anterior ao ajuste de token de uso unico por chamada concorrente.
- No estado atual do teste E2E, o artefato equivalente e `01_tokens.json`.

Origem:
- Run ID: `23096919987`
- Artifact ID: `5927065475`
- Data: `2026-03-14`

Objetivo da evidencia:
- Comprovar execucao E2E pos-deploy em ambiente real da API.
- Demonstrar sucesso nas consultas com `refinar_busca=false` e `refinar_busca=true`.
