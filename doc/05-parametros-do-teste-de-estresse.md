## Objetivo
Consolidar os parametros do teste de estresse atual em Docker para permitir metrificacao padronizada de CPU/RAM e comparacao entre execucoes.

Data de referencia desta configuracao: **22/03/2026**.

## Regra de precedencia de parametros
Nos testes com Docker Compose, o valor efetivo pode vir de:
1. variavel passada no comando (ex.: `BOT_MAX_CONSULTAS_POR_BROWSER=4 ...`);
2. arquivo `.env` do projeto;
3. default definido no compose (`${VAR:-default}`).

Exemplo atual do projeto: `.env` possui `BOT_MAX_CONSULTAS_POR_BROWSER=4`, portanto esse tende a ser o valor efetivo quando nao sobrescrito.

## Escopo dos testes disponiveis (estado real)
- Ambiente de execucao: container Docker com limite de **3 CPU** e **2 GB RAM**.
- Coleta automatica: script [`scripts/run_stress_monitor.sh`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/scripts/run_stress_monitor.sh).
- Saida de monitoramento: CSV de `docker stats` + logs do container.

Modo atual:
1. Bot direto (sem API)
   - Compose: [`docker-compose.bot-stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.bot-stress.yml)
   - Runner: [`scripts/run_bot_batch.py`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/scripts/run_bot_batch.py)
   - Observacao: roda consultas do bot direto, sem HTTP.

## Parametros de infraestrutura (docker-compose.bot-stress.yml)
Fonte: [`docker-compose.bot-stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.bot-stress.yml)

| Parametro | Valor atual | Impacto na metrica |
|---|---:|---|
| `cpus` | `3.0` | Define teto de CPU disponivel para o container. |
| `mem_limit` | `2g` | Define teto de memoria RAM disponivel. |
| `memswap_limit` | `2g` | Impede uso adicional de swap alem do limite de memoria. |
| `restart` | `no` | Nao reinicia automaticamente apos falha (falhas aparecem claramente no teste). |

## Parametros de runtime da aplicacao no teste
Fontes:
- [`docker-compose.bot-stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.bot-stress.yml)
- [`Dockerfile`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/Dockerfile)

| Parametro | Valor atual | Impacto na metrica |
|---|---:|---|
| `BOT_MAX_CONSULTAS_POR_BROWSER` | `4` | Limita quantas consultas paralelas rodam por abas (browser fixo em 1). |
| `BOT_HEADLESS` | `true` | Execucao sem interface grafica. |
| `PYTHONPATH` | `/app` | Garante importacao dos modulos do projeto no container. |

## Parametros do script de monitoramento
Fonte: [`scripts/run_stress_monitor.sh`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/scripts/run_stress_monitor.sh)

| Parametro | Default atual | Impacto na metrica |
|---|---:|---|
| `COMPOSE_FILE` | `docker-compose.bot-stress.yml` | Define qual stack sera monitorada. |
| `SERVICE_NAME` | `bot-stress` | Define qual servico sera observado. |
| `DURATION_SECONDS` | `300` | Janela total de observacao (5 min). |
| `SAMPLE_INTERVAL_SECONDS` | `2` | Frequencia de coleta (`docker stats` a cada 2s). |
| `OUT_BASE_DIR` | `logs/stress` | Pasta base dos artefatos de teste. |
| `AUTO_DOWN` | `1` | Derruba stack ao fim do teste (isola execucoes). |
| `STRESS_LOAD_COMMAND` | vazio | Opcional; em modo bot direto normalmente fica vazio. |

## Parametros de execucao do bot direto (sem API)
Fontes:
- [`docker-compose.bot-stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.bot-stress.yml)
- [`scripts/run_bot_batch.py`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/scripts/run_bot_batch.py)

| Parametro | Default atual | Impacto |
|---|---:|---|
| `BOT_CONSULTA` | `04031769644` | Consulta unica padrao quando `BOT_CONSULTAS_JSON` nao for informado. |
| `BOT_CONSULTAS_JSON` | vazio | Lista de consultas (JSON) para lote (1..N). |
| `BOT_REFINAR_BUSCA` | `true` | Ativa/desativa fluxo refinado do bot. |
| `BOT_HEADLESS` | `true` | Execucao sem interface grafica. |
| `BOT_INCLUIR_BASE64` | `false` | Remove evidencias Base64 no retorno do stress runner quando `false`. |
| `BOT_MAX_CONSULTAS_POR_BROWSER` | `4` | Quantidade de consultas paralelas por abas (browser fixo em 1). |
| `BOT_OUTPUT_DIR` | `output/stress-bot` | JSON consolidado de resultado do lote. |
| `BOT_PLAYWRIGHT_SLOW_MO_MS` | `20` | Delay entre acoes do navegador no modo stress sem API. |
| `BOT_PLAYWRIGHT_BLOCK_RESOURCE_TYPES` | `font,media` | Bloqueia recursos pesados por tipo sem impactar imagens/evidencias por padrao. |
| `BOT_PLAYWRIGHT_BLOCK_IMAGE_MODE` | `third_party` | Quando `image` estiver bloqueado, permite imagens do dominio principal para reduzir quebra. |
| `BOT_PLAYWRIGHT_PRIMARY_DOMAIN` | `portaldatransparencia.gov.br` | Dominio considerado first-party no modo `third_party`. |
| `BOT_PLAYWRIGHT_IMAGE_ALLOW_PATTERNS` | `captcha,challenge,recaptcha,hcaptcha,cloudflare,human` | Padrões de URL de imagem que nunca devem ser bloqueados. |

Persistencia no host (modo bot direto):
- `./output` (host) mapeado para `/app/output` (container)
- `./logs` (host) mapeado para `/app/logs` (container)

Exemplo (bot direto, 1 consulta):
```bash
COMPOSE_FILE=docker-compose.bot-stress.yml ./scripts/run_stress_monitor.sh
```

Exemplo (bot direto, 3 consultas):
```bash
BOT_CONSULTAS_JSON='["A DILA DA SILVA BRITO LIMA","BA N TCHI OLIVE CONFORTE N DAH KOUAGOU","CAA SANTOS BARROS MACHADO"]' \
BOT_MAX_CONSULTAS_POR_BROWSER=4 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
./scripts/run_stress_monitor.sh
```

Exemplo (3 consultas simultaneas, `refinar_busca=false`):
```bash
BOT_CONSULTAS_JSON='["A DILA DA SILVA BRITO LIMA","BA N TCHI OLIVE CONFORTE N DAH KOUAGOU","CAA SANTOS BARROS MACHADO"]' \
BOT_REFINAR_BUSCA=false \
BOT_MAX_CONSULTAS_POR_BROWSER=4 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
./scripts/run_stress_monitor.sh
```

Exemplo (3 consultas simultaneas, `refinar_busca=true`):
```bash
BOT_CONSULTAS_JSON='["A DILA DA SILVA BRITO LIMA","BA N TCHI OLIVE CONFORTE N DAH KOUAGOU","CAA SANTOS BARROS MACHADO"]' \
BOT_REFINAR_BUSCA=true \
BOT_MAX_CONSULTAS_POR_BROWSER=4 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
./scripts/run_stress_monitor.sh
```

## Roteiro inicial de teste (simples)
Executar em duas etapas com a mesma consulta, mudando apenas `BOT_REFINAR_BUSCA`.

1. Consulta unica com `refine=false`
```bash
BOT_CONSULTA='D ANGELA ALVES DE BARROS FELIPE' \
BOT_REFINAR_BUSCA=false \
BOT_MAX_CONSULTAS_POR_BROWSER=1 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
./scripts/run_stress_monitor.sh
```

2. Consulta unica com `refine=true`
```bash
BOT_CONSULTA='D ANGELA ALVES DE BARROS FELIPE' \
BOT_REFINAR_BUSCA=true \
BOT_MAX_CONSULTAS_POR_BROWSER=1 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
./scripts/run_stress_monitor.sh
```

Observacao:
- cada execucao gera uma pasta nova em `logs/stress/<timestamp>/`;
- compare principalmente `docker_stats.csv` (CPU/RAM) e `container.log` entre os dois cenarios.

## Artefatos gerados por execucao
Pasta por run: `logs/stress/<timestamp>/`

- `docker_stats.csv`: serie temporal de `cpu_perc`, `mem_usage`, `mem_perc`, `net_io`, `block_io`, `pids`.
- `container.log`: logs da aplicacao no container.
- `load.log`: logs do comando de carga (quando `STRESS_LOAD_COMMAND` e informado).
- `meta.txt`: metadados da execucao (duracao, intervalo, container, timestamps).

Artefatos de extracao do bot (modo sem API), persistidos no host:
- `output/stress-bot/batch_result_<run_id>.json`: resultado consolidado do lote.
- `output/stress-bot/item_<n>_<consulta>_<run_id>.json`: resultado individual por consulta.

Organizacao por consulta no JSON consolidado:
- campo `demarcacao_consultas`: lista com marcacao explicita (`consulta_1`, `consulta_2`, ...), status, auditoria e arquivo individual.
- campo `resultados`: mantido para compatibilidade, agora com `consulta_ordem` em cada item.
- layout interno de `resultado.pessoa`/`resultado.beneficios` nao e alterado.

Organizacao por beneficio no JSON individual:
- cada item em `beneficios` inclui `beneficio_ordem` (`beneficio_1`, `beneficio_2`, ...) e `indice_beneficio`.
- os campos antigos permanecem, sem quebra de compatibilidade.

Recomendacao operacional (anti-bloqueio x desempenho):
- evitar `slow_mo=0` como padrao em ambiente real; preferir `20` a `50` ms para reduzir assinatura de bot.
- bloqueio de recursos em stress: usar `font,media` por padrao.
- para usar `image` sem quebrar tanto o fluxo: manter `BOT_PLAYWRIGHT_BLOCK_IMAGE_MODE=third_party`.
- se quiser agressivo para benchmark bruto: `BOT_PLAYWRIGHT_BLOCK_IMAGE_MODE=all`, ciente de maior risco de falha.

Desafio tecnico resolvido (consulta por digitos, `refinar_busca=false`):
- causa raiz identificada: `slow_mo` muito baixo impede estabilizacao do resultado apos digitacao.
- sintoma observado: contador retornando `10000` resultados (quando o esperado era `1`) e abertura de item incorreto.
- solucao adotada: manter `BOT_PLAYWRIGHT_SLOW_MO_MS` entre `20` e `50` no modo sem refine.

## O que metrificar para comparacao entre execucoes
Minimo recomendado por rodada:

1. `CPU pico (%)` e `CPU medio (%)` no periodo total.
2. `RAM pico (MiB)` e `RAM media (MiB)` no periodo total.
3. `Tempo total do teste (s)` e `intervalo de amostragem (s)`.
4. `Tipo/intensidade de carga` (comando usado em `STRESS_LOAD_COMMAND`).
5. `Taxa de sucesso/erro` da API no periodo (via `load.log` ou cliente de carga).

## Protocolo padrao de teste (sugestao)
1. Rodar baseline sem carga:
   - `./scripts/run_stress_monitor.sh`
2. Rodar carga controlada:
   - `DURATION_SECONDS=600 SAMPLE_INTERVAL_SECONDS=1 STRESS_LOAD_COMMAND='<comando_de_carga>' ./scripts/run_stress_monitor.sh`
3. Comparar baseline vs carga nas quatro metricas principais:
   - CPU medio/pico
   - RAM media/pico
4. Registrar observacoes de estabilidade:
   - timeout, erro HTTP, reinicio do container, OOMKilled, queda de throughput.

## Observacao importante para este projeto
O teste limita corretamente o hardware do container para simulacao (`3 CPU`/`2GB`) em ambos os modos.
- No modo API, a qualidade da metrificacao depende da carga aplicada em `STRESS_LOAD_COMMAND`.
- No modo bot direto, a carga e definida pelas consultas passadas em `BOT_CONSULTA`/`BOT_CONSULTAS_JSON`.

Licao de estabilidade (validada em 21/03/2026):
- para busca por nome em `refinar_busca=false`, `wait_for_load_state("networkidle")` pode ficar pendente.
- estrategia adotada: tolerar timeout de `networkidle` e continuar sincronizacao pelo contador `#countResultados`.

## Benchmark exploratorio registrado (22/03/2026) - multi-browser
Objetivo desta rodada:
- comparar `4/2` vs `8/1` com o mesmo lote de **8 consultas**;
- validar comportamento em condicao real de servidor (`BOT_HEADLESS=true`);
- registrar custo de CPU/RAM e estabilidade funcional.

Nota historica:
- esta rodada foi executada quando ainda existia o parametro legado `BOT_MAX_BROWSERS`.
- no estado atual do projeto, a execucao operacional e sempre com browser fixo em `1`.

Parametros fixos dos dois cenarios:
- `BOT_HEADLESS=true`
- `BOT_REFINAR_BUSCA=false`
- `BOT_INCLUIR_BASE64=false`
- limite de infraestrutura do container: `3 CPU` e `2 GB RAM`

Consultas utilizadas (primeiras 8 da `DEFAULT_TEST_CONSULTAS`):
- `A DILA DA SILVA BRITO LIMA`
- `BA N TCHI OLIVE CONFORTE N DAH KOUAGOU`
- `CAA SANTOS BARROS MACHADO`
- `D ANGELA ALVES DE BARROS FELIPE`
- `E DILA LARISSA RODRIGUES BERTOLDO`
- `F MAGNIFICAT ZINSOU`
- `GAABI OLIVEIRA DE MESQUITA`
- `HA MOHAMMAD OLIUR RAHMAN`

Comandos executados:
```bash
# Cenario 4/2
BOT_CONSULTAS_JSON='["A DILA DA SILVA BRITO LIMA","BA N TCHI OLIVE CONFORTE N DAH KOUAGOU","CAA SANTOS BARROS MACHADO","D ANGELA ALVES DE BARROS FELIPE","E DILA LARISSA RODRIGUES BERTOLDO","F MAGNIFICAT ZINSOU","GAABI OLIVEIRA DE MESQUITA","HA MOHAMMAD OLIUR RAHMAN"]' \
BOT_REFINAR_BUSCA=false \
BOT_INCLUIR_BASE64=false \
BOT_HEADLESS=true \
BOT_MAX_BROWSERS=2 \
BOT_MAX_CONSULTAS_POR_BROWSER=4 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
OUT_BASE_DIR=logs/stress/benchmark-4x2 \
./scripts/run_stress_monitor.sh

# Cenario 8/1
BOT_CONSULTAS_JSON='["A DILA DA SILVA BRITO LIMA","BA N TCHI OLIVE CONFORTE N DAH KOUAGOU","CAA SANTOS BARROS MACHADO","D ANGELA ALVES DE BARROS FELIPE","E DILA LARISSA RODRIGUES BERTOLDO","F MAGNIFICAT ZINSOU","GAABI OLIVEIRA DE MESQUITA","HA MOHAMMAD OLIUR RAHMAN"]' \
BOT_REFINAR_BUSCA=false \
BOT_INCLUIR_BASE64=false \
BOT_HEADLESS=true \
BOT_MAX_BROWSERS=1 \
BOT_MAX_CONSULTAS_POR_BROWSER=8 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
OUT_BASE_DIR=logs/stress/benchmark-8x1 \
./scripts/run_stress_monitor.sh
```

Artefatos desta rodada:
- Cenario `4/2`: `logs/stress/benchmark-4x2/20260322_174223/`
- Cenario `8/1`: `logs/stress/benchmark-8x1/20260322_174626/`
- Consolidado `4/2`: `output/stress-bot/batch_result_20260322_204442.json`
- Consolidado `8/1`: `output/stress-bot/batch_result_20260322_204630.json`

### Resultado resumido
| Metrica | 4/2 (2 browsers x 4) | 8/1 (1 browser x 8) | Leitura |
|---|---:|---:|---|
| Duracao total (`duracao_total_ms`) | `58.741 ms` | `55.089 ms` | `8/1` ligeiramente mais rapido |
| Sucesso funcional | `4 ok / 4 error` | `1 ok / 7 error` | `4/2` mais estavel |
| CPU media | `163.73%` | `133.82%` | `8/1` mais leve |
| CPU pico | `308.16%` | `305.95%` | praticamente equivalente |
| RAM media | `56.58%` | `46.34%` | `8/1` mais leve |
| RAM pico | `99.73%` (`1.995 GiB`) | `98.78%` (`1.976 GiB`) | ambos quase no teto de 2 GB |
| PIDs medio | `291.48` | `209.68` | `8/1` mais leve |
| PIDs pico | `441` | `328` | `8/1` mais leve |

### Conclusao tecnica desta rodada
- Em **consumo de hardware (CPU/RAM)**, o cenario que se saiu melhor foi **`8/1`**.
- Em **estabilidade funcional de raspagem**, o cenario que se saiu melhor foi **`4/2`**.
- Leitura operacional da rodada: a diferenca de tempo total foi pequena, mas a diferenca de sucesso foi grande.
- Sinal de saturacao: os dois cenarios encostaram no limite de memoria do container (aprox. 2 GB), indicando que o gargalo de RAM continua relevante.

## Benchmark decisivo registrado (22/03/2026) - concorrencia reduzida
Objetivo desta rodada:
- validar estabilidade reduzindo a pressao de concorrencia;
- comparar `4/1` vs `2/2` no mesmo lote de 8 consultas;
- decidir configuracao padrao da API e do runner.

Nota:
- esta rodada foi executada antes da remocao definitiva do parametro `BOT_MAX_BROWSERS`; os valores estao mantidos aqui apenas como historico de evidencia.
- no estado atual do projeto, os comandos abaixo servem apenas para rastreabilidade de benchmark antigo.

Comandos executados:
```bash
# Cenario 4/1
BOT_CONSULTAS_JSON='["A DILA DA SILVA BRITO LIMA","BA N TCHI OLIVE CONFORTE N DAH KOUAGOU","CAA SANTOS BARROS MACHADO","D ANGELA ALVES DE BARROS FELIPE","E DILA LARISSA RODRIGUES BERTOLDO","F MAGNIFICAT ZINSOU","GAABI OLIVEIRA DE MESQUITA","HA MOHAMMAD OLIUR RAHMAN"]' \
BOT_REFINAR_BUSCA=false \
BOT_INCLUIR_BASE64=false \
BOT_HEADLESS=true \
BOT_MAX_BROWSERS=1 \
BOT_MAX_CONSULTAS_POR_BROWSER=4 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
OUT_BASE_DIR=logs/stress/benchmark-4x1 \
./scripts/run_stress_monitor.sh

# Cenario 2/2
BOT_CONSULTAS_JSON='["A DILA DA SILVA BRITO LIMA","BA N TCHI OLIVE CONFORTE N DAH KOUAGOU","CAA SANTOS BARROS MACHADO","D ANGELA ALVES DE BARROS FELIPE","E DILA LARISSA RODRIGUES BERTOLDO","F MAGNIFICAT ZINSOU","GAABI OLIVEIRA DE MESQUITA","HA MOHAMMAD OLIUR RAHMAN"]' \
BOT_REFINAR_BUSCA=false \
BOT_INCLUIR_BASE64=false \
BOT_HEADLESS=true \
BOT_MAX_BROWSERS=2 \
BOT_MAX_CONSULTAS_POR_BROWSER=2 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
OUT_BASE_DIR=logs/stress/benchmark-2x2 \
./scripts/run_stress_monitor.sh
```

Artefatos desta rodada:
- Cenario `4/1`: `logs/stress/benchmark-4x1/20260322_175514/`
- Cenario `2/2`: `logs/stress/benchmark-2x2/20260322_175723/`
- Consolidado `4/1`: `output/stress-bot/batch_result_20260322_205519.json`
- Consolidado `2/2`: `output/stress-bot/batch_result_20260322_205727.json`

### Resultado resumido
| Metrica | 4/1 (1 browser x 4 abas) | 2/2 (2 browsers x 2 abas) | Leitura |
|---|---:|---:|---|
| Duracao total (`duracao_total_ms`) | `85.640 ms` | `75.163 ms` | `2/2` mais rapido |
| Sucesso funcional | `8 ok / 0 error` | `8 ok / 0 error` | ambos estaveis |
| CPU media | `169.18%` | `184.09%` | `4/1` mais leve |
| CPU pico | `313.12%` | `315.75%` | equivalente |
| RAM media | `54.59%` | `60.75%` | `4/1` mais leve |
| RAM pico | `94.94%` | `92.78%` | equivalente |
| PIDs medio | `216.41` | `313.88` | `4/1` mais leve |
| PIDs pico | `309` | `425` | `4/1` mais leve |

### Decisao tecnica vigente
- A API e o stress runner passam a operar com **browser fixo em 1**.
- O unico fallback/configuracao de paralelismo fica em **`BOT_MAX_CONSULTAS_POR_BROWSER`** (abas simultaneas), com default `4`.
- A configuracao de quantidade de browsers foi removida para evitar picos de RAM e excesso de processos.
- Limite de infraestrutura (`cpus`, `mem_limit`, `memswap_limit`) permanece fixo no compose, sem parametrizacao por env.

### Validacao pos-ajuste (22/03/2026)
Objetivo:
- confirmar o comportamento apos remocao do parametro `BOT_MAX_BROWSERS` no codigo/configuracao executavel (confirmado);
- validar coerencia do retorno em lote.

Execucao registrada:
- pasta de metricas: `logs/stress/benchmark-fixed-1x4/20260322_180945/`
- consolidado: `output/stress-bot/batch_result_20260322_210950.json`
- parametros: `BOT_HEADLESS=true`, `BOT_REFINAR_BUSCA=false`, `BOT_INCLUIR_BASE64=false`, `BOT_MAX_CONSULTAS_POR_BROWSER=4`

Resultado:
- `8/8` consultas com `status=ok` (zero erros).
- coerencia do payload: `id_consulta`, `data_hora_consulta`, `pessoa` e `beneficios[]` presentes em todos os itens.
- duracao total: `77.320 ms`.
- consumo: `CPU media 178.69%`, `CPU pico 311.93%`, `RAM media 55.49%`, `RAM pico 84.61%`.
