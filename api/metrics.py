from prometheus_client import Counter, Histogram


API_CONSULTA_REQUESTS_TOTAL = Counter(
    "most_api_consulta_requests_total",
    "Total de requisicoes no endpoint /api/consulta por modo de payload.",
    labelnames=("mode",),
)

API_CONSULTA_BATCH_SIZE = Histogram(
    "most_api_consulta_batch_size",
    "Quantidade de consultas enviadas por requisicao batch.",
    buckets=(1, 2, 3, float("inf")),
)

API_CONSULTA_DURATION_SECONDS = Histogram(
    "most_api_consulta_duration_seconds",
    "Tempo total de processamento da requisicao /api/consulta.",
    labelnames=("mode",),
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, float("inf")),
)

API_CONSULTA_ITEM_DURATION_SECONDS = Histogram(
    "most_api_consulta_item_duration_seconds",
    "Tempo de processamento por consulta individual (single ou item de batch).",
    labelnames=("mode", "status"),
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60, 120, float("inf")),
)

API_CONSULTA_ITEM_STATUS_TOTAL = Counter(
    "most_api_consulta_item_status_total",
    "Total de consultas processadas por status funcional.",
    labelnames=("mode", "status"),
)

API_CONSULTA_RESULT_KIND_TOTAL = Counter(
    "most_api_consulta_result_kind_total",
    "Total de consultas por tipo de resultado: info (com dados) ou problem (erro/sem dados).",
    labelnames=("mode", "kind"),
)


def classify_result_kind(status: str) -> str:
    status_norm = str(status or "").lower()
    if status_norm == "ok":
        return "info"
    return "problem"
