# Observabilidade (Prometheus) - Guia de uso

Este documento descreve como operar e interpretar as métricas expostas pela API Django para o Prometheus.

## Objetivo da fase 1
- Expor métricas da aplicação em `GET /metrics`.
- Coletar essas métricas via Prometheus.
- Validar saúde, volume, erro e latência da API.

## Arquivos da implementação
- `web/settings.py`: instrumentação do Django (`django_prometheus` app e middlewares).
- `web/urls.py`: endpoint de métricas (`/metrics`).
- `docker-compose.prometheus.yml`: serviço local do Prometheus.
- `monitoring/prometheus/prometheus.yml`: configuração de scrape.

## Subida local (resumo)
1. Subir API:
```bash
python manage.py runserver 0.0.0.0:8000
```
2. Subir Prometheus:
```bash
docker compose -f docker-compose.prometheus.yml up -d
```
3. Abrir UI:
- `http://127.0.0.1:9090`
- Menu `Status > Targets` (job `most-rpa-api` deve estar `UP`)

## Catálogo de métricas (atual)

### 1) Saúde do alvo
- Métrica: `up{job="most-rpa-api"}`
- Tipo: gauge
- Interpretação:
- `1` = alvo coletado com sucesso
- `0` = falha de coleta

### 2) Runtime Python
- Prefixos: `python_*`
- Exemplos:
- `python_info`
- `python_gc_collections_total`
- `python_gc_objects_collected_total`
- Uso: diagnóstico de runtime/GC.

### 3) Processo da aplicação
- Prefixos: `process_*`
- Exemplos:
- `process_cpu_seconds_total`
- `process_virtual_memory_bytes`
- `process_resident_memory_bytes`
- Uso: CPU e memória do processo.

### 4) HTTP Django - requisições
- Métricas principais:
- `django_http_requests_total_by_method_total`
- `django_http_requests_total_by_view_transport_method_total`
- Uso: volume de tráfego por método/view.

### 5) HTTP Django - respostas
- Métricas principais:
- `django_http_responses_total_by_status_total`
- Uso: volume por status HTTP (2xx, 4xx, 5xx).

### 6) HTTP Django - latência
- Métricas principais:
- `django_http_request_duration_seconds_bucket`
- `django_http_request_duration_seconds_sum`
- `django_http_request_duration_seconds_count`
- Uso: percentis e tempo médio de resposta.

## Queries PromQL prontas (para operação)

### Saúde do alvo
```promql
up{job="most-rpa-api"}
```

### Requisições por segundo (RPS)
```promql
sum(rate(django_http_requests_total_by_method_total[5m]))
```

### Requisições por minuto
```promql
sum(increase(django_http_requests_total_by_method_total[1m]))
```

### Erros 4xx/5xx por minuto
```promql
sum(increase(django_http_responses_total_by_status_total{status=~"4..|5.."}[1m]))
```

### Latência p95
```promql
histogram_quantile(0.95, sum(rate(django_http_request_duration_seconds_bucket[5m])) by (le))
```

### Latência média
```promql
sum(rate(django_http_request_duration_seconds_sum[5m])) / sum(rate(django_http_request_duration_seconds_count[5m]))
```

## Descoberta de métricas disponíveis
Para listar os nomes reais de métricas no ambiente atual:
```bash
curl -s http://127.0.0.1:8000/metrics | awk '/^# TYPE/{print $3}' | sort -u
```

Para listar somente métricas Django:
```bash
curl -s http://127.0.0.1:8000/metrics | grep '^django_' | head -n 100
```

## Dicas de interpretação
- Métricas `*_total` são acumuladas: use `rate()` ou `increase()` para leitura operacional.
- Se um gráfico mostrar `No data`, confirme:
- target `UP`
- janela de tempo (ex.: últimos 15m)
- nome exato da métrica
- `up=1` não significa app saudável no negócio, apenas que o scrape funcionou.


## Próximas fases
- Fase 2: Grafana (dashboards operacionais).
- Fase 3: Alertmanager + Telegram (alertas acionáveis).
