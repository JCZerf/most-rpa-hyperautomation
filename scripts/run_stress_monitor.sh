#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.bot-stress.yml}"
SERVICE_NAME="${SERVICE_NAME:-bot-stress}"
DURATION_SECONDS="${DURATION_SECONDS:-300}"
SAMPLE_INTERVAL_SECONDS="${SAMPLE_INTERVAL_SECONDS:-2}"
OUT_BASE_DIR="${OUT_BASE_DIR:-logs/stress}"
AUTO_DOWN="${AUTO_DOWN:-1}"
STRESS_LOAD_COMMAND="${STRESS_LOAD_COMMAND:-}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Erro: docker nao encontrado no PATH."
  exit 1
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Erro: arquivo de compose nao encontrado: $COMPOSE_FILE"
  exit 1
fi

mkdir -p "$OUT_BASE_DIR"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
RUN_DIR="$OUT_BASE_DIR/$RUN_ID"
mkdir -p "$RUN_DIR"

STATS_CSV="$RUN_DIR/docker_stats.csv"
APP_LOG_FILE="$RUN_DIR/container.log"
LOAD_LOG_FILE="$RUN_DIR/load.log"
META_FILE="$RUN_DIR/meta.txt"

LOAD_PID=""
LOGS_PID=""

cleanup() {
  local exit_code="$?"

  if [[ -n "$LOAD_PID" ]] && kill -0 "$LOAD_PID" >/dev/null 2>&1; then
    kill "$LOAD_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "$LOGS_PID" ]] && kill -0 "$LOGS_PID" >/dev/null 2>&1; then
    kill "$LOGS_PID" >/dev/null 2>&1 || true
  fi

  if [[ "$AUTO_DOWN" == "1" ]]; then
    docker compose -f "$COMPOSE_FILE" down >/dev/null 2>&1 || true
  fi

  exit "$exit_code"
}
trap cleanup EXIT INT TERM

echo "Subindo container para teste de estresse..."
docker compose -f "$COMPOSE_FILE" up -d --build

CONTAINER_ID="$(docker compose -f "$COMPOSE_FILE" ps -q "$SERVICE_NAME")"
if [[ -z "$CONTAINER_ID" ]]; then
  echo "Erro: nao foi possivel identificar o container do servico '$SERVICE_NAME'."
  exit 1
fi

CONTAINER_NAME="$(docker inspect --format '{{.Name}}' "$CONTAINER_ID" | sed 's#^/##')"

{
  echo "run_id=$RUN_ID"
  echo "compose_file=$COMPOSE_FILE"
  echo "service_name=$SERVICE_NAME"
  echo "container_id=$CONTAINER_ID"
  echo "container_name=$CONTAINER_NAME"
  echo "duration_seconds=$DURATION_SECONDS"
  echo "sample_interval_seconds=$SAMPLE_INTERVAL_SECONDS"
  echo "auto_down=$AUTO_DOWN"
  echo "started_at=$(date -Iseconds)"
} >"$META_FILE"

echo "timestamp,container,cpu_perc,mem_usage,mem_perc,net_io,block_io,pids" >"$STATS_CSV"

docker logs -f "$CONTAINER_ID" >"$APP_LOG_FILE" 2>&1 &
LOGS_PID="$!"

if [[ -n "$STRESS_LOAD_COMMAND" ]]; then
  echo "Executando carga em paralelo: $STRESS_LOAD_COMMAND"
  bash -lc "$STRESS_LOAD_COMMAND" >"$LOAD_LOG_FILE" 2>&1 &
  LOAD_PID="$!"
fi

echo "Coletando metricas por $DURATION_SECONDS segundos (intervalo ${SAMPLE_INTERVAL_SECONDS}s)..."
start_ts="$(date +%s)"
while true; do
  now_ts="$(date +%s)"
  elapsed="$((now_ts - start_ts))"
  if (( elapsed >= DURATION_SECONDS )); then
    break
  fi

  timestamp="$(date -Iseconds)"
  stats_line="$(docker stats --no-stream --format '{{.Container}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}' "$CONTAINER_ID" || true)"

  if [[ -n "$stats_line" ]]; then
    echo "$timestamp,$stats_line" >>"$STATS_CSV"
  fi

  running_state="$(docker inspect -f '{{.State.Running}}' "$CONTAINER_ID" 2>/dev/null || echo false)"
  if [[ "$running_state" != "true" ]]; then
    echo "Container finalizou antes do tempo limite; encerrando coleta."
    break
  fi

  sleep "$SAMPLE_INTERVAL_SECONDS"
done

container_exit_code="$(docker inspect -f '{{.State.ExitCode}}' "$CONTAINER_ID" 2>/dev/null || echo unknown)"
container_finished_at="$(docker inspect -f '{{.State.FinishedAt}}' "$CONTAINER_ID" 2>/dev/null || echo unknown)"
echo "container_exit_code=$container_exit_code" >>"$META_FILE"
echo "container_finished_at=$container_finished_at" >>"$META_FILE"
echo "finished_at=$(date -Iseconds)" >>"$META_FILE"
echo "Coleta finalizada."
echo "Arquivos gerados em: $RUN_DIR"
echo "- Metricas CSV: $STATS_CSV"
echo "- Logs do container: $APP_LOG_FILE"
if [[ -n "$STRESS_LOAD_COMMAND" ]]; then
  echo "- Logs de carga: $LOAD_LOG_FILE"
fi
