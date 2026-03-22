# Observabilidade (Prometheus + Grafana) - Guia de uso

Este documento descreve como operar e interpretar as métricas expostas pela API Django no stack de observabilidade local com Prometheus e Grafana.

## Objetivo da fase 1
- Expor métricas da aplicação em `GET /metrics`.
- Coletar essas métricas via Prometheus.
- Validar saúde, volume, erro e latência da API.

## Objetivo da fase 2
- Visualizar as métricas em dashboards legíveis no Grafana.
- Reduzir dependência de consultas manuais no Prometheus.

## Objetivo da fase 3
- Alertas automáticos no Grafana com regras versionadas.
- Template de notificação versionado para reutilizar em Telegram/e-mail.
- Contact point e policy configurados manualmente na UI.

## Arquivos da implementação
- `web/settings.py`: instrumentação do Django (`django_prometheus` app e middlewares).
- `web/urls.py`: endpoint de métricas (`/metrics`).
- `docker-compose.observability.yml`: stack local com Prometheus + Grafana.
- `docker-compose.observability.alerting-bootstrap.yml`: habilita provisioning automático de alertas (opcional).
- `monitoring/prometheus/prometheus.yml`: configuração de scrape.
- `monitoring/grafana/provisioning/datasources/prometheus.yml`: datasource provisionado.
- `monitoring/grafana/provisioning/dashboards/dashboards.yml`: provider de dashboards.
- `monitoring/grafana/dashboards/most-rpa-api-overview.json`: dashboard inicial.
- `monitoring/grafana/provisioning/alerting/templates.yml`: template versionado para notificações.
- `monitoring/grafana/provisioning/alerting/alert-rules.yml`: regras versionadas (referência para import/manual).

## Subida local (Prometheus + Grafana)
1. Subir API:
```bash
python manage.py runserver 0.0.0.0:8000
```
2. Subir stack de observabilidade:
```bash
docker compose -f docker-compose.observability.yml up -d
```
3. Recriar o Grafana após mudanças de configuração:
```bash
docker compose -f docker-compose.observability.yml up -d --force-recreate grafana
```
4. Opcional: bootstrap automático de alertas versionados:
```bash
docker compose -f docker-compose.observability.yml -f docker-compose.observability.alerting-bootstrap.yml up -d --force-recreate grafana
```
5. Abrir UIs:
- Prometheus: `http://127.0.0.1:9090`
- Grafana: `http://127.0.0.1:3000`
6. Login padrão Grafana (local):
- usuário: `admin`
- senha: `admin`
7. Dashboard provisionado:
- pasta: `Most RPA`
- dashboard: `Most RPA - API Overview`
8. Observação importante:
- O compose padrão **não aplica alertas provisionados** automaticamente (modo manual).
- O compose de bootstrap aplica regras/templates da pasta `monitoring/grafana/provisioning/alerting`.
9. Configuração manual de alertas e notificação (UI Grafana):
- criar/importar regras com base no arquivo `monitoring/grafana/provisioning/alerting/alert-rules.yml`
- criar o contact point (Telegram, e-mail, etc.)
- criar/ajustar notification policy para rotear os alertas
- aplicar template `telegram.default` (arquivo `monitoring/grafana/provisioning/alerting/templates.yml`) no canal desejado

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

### 7) Banco de dados
- Nesta aplicação, não há banco de dados operacional para o fluxo principal.
- O `django_db_*` não é foco da observabilidade atual.

## Métricas de negócio (custom do projeto)

### 1) Quantidade de requisições no endpoint de consulta
- Métrica: `most_api_consulta_requests_total{mode="single|batch_consultas|batch_itens"}`
- Tipo: counter
- Uso: volume de chamadas por tipo de payload.

### 2) Quantidade de consultas por requisição (batch)
- Métrica: `most_api_consulta_batch_size`
- Tipo: histogram
- Uso: distribuição do tamanho dos lotes (1, 2, 3).

### 3) Tempo total para entrega da resposta (request completo)
- Métrica: `most_api_consulta_duration_seconds{mode="..."}`
- Tipo: histogram
- Uso: medir SLA/SLO da API.

### 4) Velocidade por consulta individual
- Métrica: `most_api_consulta_item_duration_seconds{mode="...",status="ok|not_found|invalid|error"}`
- Tipo: histogram
- Uso: tempo de cada consulta (single e itens de batch).

### 5) Taxa de sucesso por tipo de resultado
- Métrica: `most_api_consulta_result_kind_total{mode="...",kind="info|problem"}`
- Tipo: counter
- Regra:
- `kind="info"`: consulta com `status="ok"` (retornou informação útil).
- `kind="problem"`: `not_found`, `invalid` ou `error`.

### 6) Taxa por status funcional da consulta
- Métrica: `most_api_consulta_item_status_total{mode="...",status="ok|not_found|invalid|error"}`
- Tipo: counter
- Uso: visão direta de qualidade do processamento.

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

### CPU do processo
```promql
rate(process_cpu_seconds_total[5m])
```

### RAM do processo (MB)
```promql
process_resident_memory_bytes / 1024 / 1024
```

### Requisições por tipo de payload (`single`, `batch`)
```promql
sum by (mode) (rate(most_api_consulta_requests_total[5m]))
```

### Distribuição de tamanho de lote (batch)
```promql
histogram_quantile(0.95, sum(rate(most_api_consulta_batch_size_bucket[5m])) by (le))
```

### Tempo total da API (p95)
```promql
histogram_quantile(0.95, sum(rate(most_api_consulta_duration_seconds_bucket[5m])) by (le, mode))
```

### Tempo por consulta individual (p95)
```promql
histogram_quantile(0.95, sum(rate(most_api_consulta_item_duration_seconds_bucket[5m])) by (le, mode, status))
```

### Taxa de sucesso (`info`) vs problema (`problem`)
```promql
sum by (kind) (rate(most_api_consulta_result_kind_total[5m]))
```

### Taxa por status funcional (`ok`, `not_found`, `invalid`, `error`)
```promql
sum by (status) (rate(most_api_consulta_item_status_total[5m]))
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
- Métricas com sufixo `_created` são timestamps de criação (epoch), não indicadores de volume/latência.

## Segurança da rota `/metrics`
- Em ambiente local, rota aberta para facilitar operação.
- Em produção, proteger por rede (ingress interno, allowlist, VPC/firewall), sem exposição pública.


## Fase 3 - fluxo separado de alertas
- Template: `telegram.default`.
- Regras de alerta: versionadas em arquivo (`alert-rules.yml`) para importação manual.
- Contact points/policies: configuração manual na UI para manter flexibilidade por ambiente.
- O `docker-compose.observability.yml` não recria alertas a cada subida.
- Quando desejar criação automática, usar o compose de bootstrap:
  `docker-compose.observability.alerting-bootstrap.yml`.
