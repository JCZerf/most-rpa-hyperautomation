## Objetivo
Consolidar os parametros do teste de estresse atual em Docker para permitir metrificacao padronizada de CPU/RAM e comparacao entre execucoes.

Data de referencia desta configuracao: **21/03/2026**.

## Regra de precedencia de parametros
Nos testes com Docker Compose, o valor efetivo pode vir de:
1. variavel passada no comando (ex.: `BOT_MAX_WORKERS=1 ...`);
2. arquivo `.env` do projeto;
3. default definido no compose (`${VAR:-default}`).

Exemplo atual do projeto: `.env` possui `BOT_MAX_WORKERS=3`, portanto esse tende a ser o valor efetivo quando nao sobrescrito no comando.

## Escopo dos testes disponiveis (estado real)
- Ambiente de execucao (ambos): container Docker com limite de **2 CPU** e **1 GB RAM**.
- Coleta automatica (ambos): script [`scripts/run_stress_monitor.sh`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/scripts/run_stress_monitor.sh).
- Saida de monitoramento (ambos): CSV de `docker stats` + logs do container.

Modos:

1. API (Gunicorn)
   - Compose: [`docker-compose.stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.stress.yml)
   - Observacao: sem `STRESS_LOAD_COMMAND`, mede baseline/idle.
2. Bot direto (sem API)
   - Compose: [`docker-compose.bot-stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.bot-stress.yml)
   - Runner: [`scripts/run_bot_batch.py`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/scripts/run_bot_batch.py)
   - Observacao: roda consultas do bot direto, sem HTTP.

## Parametros de infraestrutura (docker-compose.stress.yml)
Fonte: [`docker-compose.stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.stress.yml)

| Parametro | Valor atual | Impacto na metrica |
|---|---:|---|
| `cpus` | `2.0` | Define teto de CPU disponivel para o container. |
| `mem_limit` | `1g` | Define teto de memoria RAM disponivel. |
| `memswap_limit` | `1g` | Impede uso adicional de swap alem do limite de memoria. |
| `ports` | `8000:8000` | Exposicao local da API para geracao de carga externa. |
| `restart` | `no` | Nao reinicia automaticamente apos falha (falhas aparecem claramente no teste). |

Os mesmos limites de recurso tambem sao usados em:
- [`docker-compose.bot-stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.bot-stress.yml)

## Parametros de runtime da aplicacao no teste
Fontes:
- [`docker-compose.stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.stress.yml)
- [`Dockerfile`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/Dockerfile)

| Parametro | Valor atual | Impacto na metrica |
|---|---:|---|
| `GUNICORN_WORKERS` | `1` | Menos paralelismo de processos; menor consumo de RAM por processo. |
| `GUNICORN_THREADS` | `2` | Concorrencia leve por threads no mesmo worker. |
| `BOT_MAX_WORKERS` | `1` | Limita paralelismo interno do bot por requisicao na API. |
| `PORT` | `8000` | Porta de escuta da aplicacao. |
| `gunicorn --timeout` | `600` (default do CMD) | Requisicoes longas nao encerram cedo; pode aumentar ocupacao de recursos sob carga. |
| `gunicorn --graceful-timeout` | `30` (default do CMD) | Tempo de finalizacao graciosa. |
| `gunicorn --keep-alive` | `65` (default do CMD) | Mantem conexoes por mais tempo; pode afetar uso de recursos em carga HTTP. |

## Parametros do script de monitoramento
Fonte: [`scripts/run_stress_monitor.sh`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/scripts/run_stress_monitor.sh)

| Parametro | Default atual | Impacto na metrica |
|---|---:|---|
| `COMPOSE_FILE` | `docker-compose.stress.yml` | Define qual stack sera monitorada. |
| `SERVICE_NAME` | `bot-stress` | Define qual servico sera observado. |
| `DURATION_SECONDS` | `300` | Janela total de observacao (5 min). |
| `SAMPLE_INTERVAL_SECONDS` | `2` | Frequencia de coleta (`docker stats` a cada 2s). |
| `OUT_BASE_DIR` | `logs/stress` | Pasta base dos artefatos de teste. |
| `AUTO_DOWN` | `1` | Derruba stack ao fim do teste (isola execucoes). |
| `STRESS_LOAD_COMMAND` | vazio | Sem carga ativa por padrao. |

## Parametros de execucao do bot direto (sem API)
Fontes:
- [`docker-compose.bot-stress.yml`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/docker-compose.bot-stress.yml)
- [`scripts/run_bot_batch.py`](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/scripts/run_bot_batch.py)

| Parametro | Default atual | Impacto |
|---|---:|---|
| `BOT_CONSULTA` | `04031769644` | Consulta unica padrao quando `BOT_CONSULTAS_JSON` nao for informado. |
| `BOT_CONSULTAS_JSON` | vazio | Lista de consultas (JSON) para lote, maximo 3. |
| `BOT_REFINAR_BUSCA` | `true` | Ativa/desativa fluxo refinado do bot. |
| `BOT_HEADLESS` | `true` | Execucao sem interface grafica. |
| `BOT_MAX_WORKERS` | `1` | Paralelismo de execucao no lote (ate quantidade de consultas). |
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
BOT_CONSULTAS_JSON='["04031769644","A ANNE CHRISTINE SILVA RIBEIRO","A LIDA PEREIRA FIALHO"]' \
COMPOSE_FILE=docker-compose.bot-stress.yml \
./scripts/run_stress_monitor.sh
```

## Roteiro inicial de teste (simples)
Executar em duas etapas com a mesma consulta, mudando apenas `BOT_REFINAR_BUSCA`.

1. Consulta unica com `refine=false`
```bash
BOT_CONSULTA='04031769644' \
BOT_REFINAR_BUSCA=false \
BOT_MAX_WORKERS=1 \
COMPOSE_FILE=docker-compose.bot-stress.yml \
./scripts/run_stress_monitor.sh
```

2. Consulta unica com `refine=true`
```bash
BOT_CONSULTA='04031769644' \
BOT_REFINAR_BUSCA=true \
BOT_MAX_WORKERS=1 \
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
- campo `demarcacao_consultas`: lista com marcacao explicita (`consulta_1`, `consulta_2`, `consulta_3`), status, auditoria e arquivo individual.
- campo `resultados`: mantido para compatibilidade, agora com `consulta_ordem` em cada item.
- layout interno de `resultado.pessoa`/`resultado.beneficios` nao e alterado.

Recomendacao operacional (anti-bloqueio x desempenho):
- evitar `slow_mo=0` como padrao em ambiente real; preferir `20` a `50` ms para reduzir assinatura de bot.
- bloqueio de recursos em stress: usar `font,media` por padrao.
- para usar `image` sem quebrar tanto o fluxo: manter `BOT_PLAYWRIGHT_BLOCK_IMAGE_MODE=third_party`.
- se quiser agressivo para benchmark bruto: `BOT_PLAYWRIGHT_BLOCK_IMAGE_MODE=all`, ciente de maior risco de falha.

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
O teste limita corretamente o hardware do container para simulacao (`2 CPU`/`1GB`) em ambos os modos.
- No modo API, a qualidade da metrificacao depende da carga aplicada em `STRESS_LOAD_COMMAND`.
- No modo bot direto, a carga e definida pelas consultas passadas em `BOT_CONSULTA`/`BOT_CONSULTAS_JSON`.
