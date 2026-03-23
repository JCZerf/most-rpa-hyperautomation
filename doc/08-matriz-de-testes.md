# Matriz de testes

Este documento resume o que cada tipo de teste cobre hoje, com foco em facilitar manutencao e onboard.

## Visao geral

| Tipo | Arquivos | Objetivo | Dependencia externa |
|---|---|---|---|
| Unitario | `tests/test_validators.py`, `tests/test_navigation.py`, `tests/test_utils.py`, `tests/test_extraction_parsers.py` | Validar regras e funcoes isoladas (entrada, parsing, score e formatacao) | Nao |
| Integracao local (API/app) | `tests/test_api_token.py`, `tests/test_api_consulta.py`, `tests/test_main.py`, `tests/test_bot.py`, `tests/test_browser_env.py` | Validar contrato interno da API e orquestracao com mocks/fakes | Nao (sem API online) |
| E2E smoke | `tests/test_e2e_smoke.py` (`@pytest.mark.e2e`) | Validar fluxo real com API online e chamadas HTTP reais | Sim |

## Cobertura por arquivo de teste

| Arquivo | Cobertura principal |
|---|---|
| `tests/test_validators.py` | Validacao de CPF/NIS/nome e casos invalidos |
| `tests/test_navigation.py` | Score de similaridade de nomes e selecao do melhor resultado |
| `tests/test_extraction_parsers.py` | Parsing de tabelas/beneficios e fallback de layout |
| `tests/test_utils.py` | Conversao e formatacao monetaria |
| `tests/test_bot.py` | Contrato final do bot (campos base, erros, evidencias, auditoria) |
| `tests/test_browser_env.py` | Leitura e comportamento de envs do contexto Playwright |
| `tests/test_main.py` | Fluxo do runner local e metadados de execucao |
| `tests/test_api_token.py` | Emissao de token, grant/scope e erros de autenticacao |
| `tests/test_api_consulta.py` | `/api/consulta/`: single/lote, auth, uso unico de token, erros e ordenacao |
| `tests/test_e2e_smoke.py` | Contrato da API online, emissao de token real e concorrencia real |

## Cenarios E2E atuais

### 1) Smoke concorrente basico
- Teste: `test_e2e_smoke_consulta_simples_e_refinada`
- Cobertura:
  - Emite 2 tokens reais (`/api/token/`)
  - Executa 2 requisicoes simultaneas (`refinar_busca=false` e `refinar_busca=true`)
  - Valida contrato HTTP/JSON da resposta
  - Gera artefatos em `output/e2e-artifacts/`

### 2) Lote reagindo aos limites da API (opcional)
- Teste: `test_e2e_smoke_lote_reage_a_limites_da_api`
- Cobertura:
  - Envia lote com N consultas em uma requisicao
  - Valida `meta_execucao.total_consultas`, `max_consultas_por_browser` e `blocos_fila`
  - Objetivo: verificar se a fila interna reage conforme o limite configurado

### 3) Requisicoes simultaneas com lote (opcional)
- Teste: `test_e2e_smoke_requisicoes_simultaneas_com_lotes`
- Cobertura:
  - Dispara multiplas requisicoes em paralelo
  - Cada requisicao leva um lote
  - Valida contrato e metadados de limite por resposta

## Como ativar cenarios E2E de limite/concurrency

Por padrao, os cenarios 2 e 3 ficam desativados para nao alongar o smoke basico.

Variaveis:
- `E2E_ENABLE_LIMITS_SCENARIOS=true` ativa os cenarios de lote/limite
- `E2E_BATCH_SIZE` tamanho do lote do cenario 2 (default `6`)
- `E2E_BATCH_REFINAR` usa `refinar_busca=true/false` no cenario 2 (default `false`)
- `E2E_PARALLEL_REQUESTS` quantidade de requisicoes simultaneas no cenario 3 (default `3`)
- `E2E_PARALLEL_BATCH_SIZE` tamanho do lote por requisicao no cenario 3 (default `4`)
- `E2E_REQUIRE_SUCCESS=true` modo estrito (exige `200` nos cenarios concorrentes)

Exemplo:

```bash
E2E_BASE_URL=... \
E2E_CLIENT_ID=... \
E2E_CLIENT_SECRET=... \
E2E_CONSULTA_BASE=... \
E2E_ENABLE_LIMITS_SCENARIOS=true \
E2E_BATCH_SIZE=8 \
E2E_PARALLEL_REQUESTS=4 \
E2E_PARALLEL_BATCH_SIZE=4 \
./venv/bin/pytest -q tests/test_e2e_smoke.py -m e2e
```

## Relacao com estresse

- O E2E acima e um smoke funcional com concorrencia controlada.
- Teste de estresse de recurso (CPU/RAM) permanece no roteiro de `scripts/run_stress_monitor.sh` e `doc/05-parametros-do-teste-de-estresse.md`.
- Recomendacao: usar E2E para regressao de contrato/fluxo e stress monitor para capacidade operacional.
