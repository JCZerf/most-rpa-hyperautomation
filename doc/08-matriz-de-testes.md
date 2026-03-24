# Matriz de testes

Este documento resume o que cada tipo de teste cobre hoje, com foco em facilitar manutencao e onboard.

## Visao geral

| Tipo | Arquivos | Objetivo | Dependencia externa |
|---|---|---|---|
| Unitario | `tests/unit/test_validators.py`, `tests/unit/test_navigation.py`, `tests/unit/test_utils.py`, `tests/unit/test_extraction_parsers.py` | Validar regras e funcoes isoladas (entrada, parsing, score e formatacao) | Nao |
| Integracao local (API/app) | `tests/integration/test_api_token.py`, `tests/integration/test_api_consulta.py`, `tests/integration/test_main.py`, `tests/integration/test_bot.py`, `tests/integration/test_browser_env.py` | Validar contrato interno da API e orquestracao com mocks/fakes | Nao (sem API online) |
| E2E smoke | `tests/e2e/test_e2e_smoke.py` (`@pytest.mark.e2e`) | Validar fluxo real com API online e chamadas HTTP reais | Sim |

## Cobertura por arquivo de teste

| Arquivo | Cobertura principal |
|---|---|
| `tests/unit/test_validators.py` | Validacao de CPF/NIS/nome e casos invalidos |
| `tests/unit/test_navigation.py` | Score de similaridade de nomes e selecao do melhor resultado |
| `tests/unit/test_extraction_parsers.py` | Parsing de tabelas/beneficios e fallback de layout |
| `tests/unit/test_utils.py` | Conversao e formatacao monetaria |
| `tests/integration/test_bot.py` | Contrato final do bot (campos base, erros, evidencias, auditoria) |
| `tests/integration/test_browser_env.py` | Leitura e comportamento de envs do contexto Playwright |
| `tests/integration/test_main.py` | Fluxo do runner local e metadados de execucao |
| `tests/integration/test_api_token.py` | Emissao de token, grant/scope e erros de autenticacao |
| `tests/integration/test_api_consulta.py` | `/api/consulta/`: single/lote, auth, uso unico de token, erros e ordenacao |
| `tests/e2e/test_e2e_smoke.py` | Contrato da API online, emissao de token real e concorrencia real |

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
  - Envia lote com N consultas reais (multiplos alvos configuraveis)
  - Suporta modo misto de `refinar_busca` (metade `false`, metade `true`) via payload `itens`
  - Valida `meta_execucao.total_consultas`, `max_consultas_por_browser` e `blocos_fila`
  - Objetivo: verificar se a fila interna reage conforme o limite configurado

### 3) Requisicoes simultaneas com lote (opcional)
- Teste: `test_e2e_smoke_requisicoes_simultaneas_com_lotes`
- Cobertura:
  - Dispara multiplas requisicoes em paralelo
  - Cada requisicao leva um lote com alvos configuraveis
  - Suporta mistura de `refinar_busca` no lote
  - Valida contrato e metadados de limite por resposta

### 4) Lote unico com 12 alvos (opcional)
- Teste: `test_e2e_smoke_lote_unico_12_alvos`
- Cobertura:
  - Dispara uma unica requisicao batch com 12 consultas
  - Usa o mesmo `E2E_BATCH_TARGETS` como pool de alvos
  - Quando o pool tiver menos de 12 alvos, reutiliza em rotacao
  - Mantem distribuicao mista de `refinar_busca` (metade false, metade true)

## Como ativar cenarios E2E de limite/concurrency

Variaveis:
- `E2E_BATCH_TARGETS` (lista separada por `;`) define os alvos usados no batch
- `E2E_REQUIRE_SUCCESS=true` modo estrito (exige `200` nos cenarios concorrentes)

Regras fixas de execucao:
- Tamanho do batch = quantidade de alvos em `E2E_BATCH_TARGETS`
- Batch misto: metade `refinar=false` e metade `refinar=true`
- Requisicoes simultaneas do cenario 3 = `4` (dobro de `2` suportadas no ambiente)

Exemplo:

```bash
E2E_BASE_URL=... \
E2E_CLIENT_ID=... \
E2E_CLIENT_SECRET=... \
E2E_CONSULTA_BASE=... \
E2E_CONSULTA_REFINADA=... \
E2E_BATCH_TARGETS='A LIDA PEREIRA FIALHO;A ANNE CHRISTINE SILVA RIBEIRO;GAABI OLIVEIRA DE MESQUITA;HAABE OLIVEIRA DA SILVA' \
./venv/bin/pytest -q tests/e2e/test_e2e_smoke.py -m e2e
```

## Relacao com estresse

- O E2E acima e um smoke funcional com concorrencia controlada.
- Teste de estresse de recurso (CPU/RAM) permanece no roteiro de `scripts/run_stress_monitor.sh` e `doc/05-parametros-do-teste-de-estresse.md`.
- Recomendacao: usar E2E para regressao de contrato/fluxo e stress monitor para capacidade operacional.
