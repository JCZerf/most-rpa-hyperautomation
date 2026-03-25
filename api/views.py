import logging
import time
from typing import List, Dict, Any

from asgiref.sync import async_to_sync

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer
from drf_spectacular.types import OpenApiTypes

from bot.core.logging_utils import log_event
from bot.runtime.orchestrator import (
    env_bool,
    executar_consultas_em_lote_async,
    get_runtime_limits,
    remover_imagens_base64,
)
from bot.core.validators import mascarar_identificador
from .auth import consume_token_once, issue_token, validate_token, scope_allows
from .metrics import (
    API_CONSULTA_REQUESTS_TOTAL,
    API_CONSULTA_BATCH_SIZE,
    API_CONSULTA_DURATION_SECONDS,
    API_CONSULTA_ITEM_DURATION_SECONDS,
    API_CONSULTA_ITEM_STATUS_TOTAL,
    API_CONSULTA_RESULT_KIND_TOTAL,
    classify_result_kind,
)

logger = logging.getLogger(__name__)

DEFAULT_INCLUDE_BASE64 = env_bool("BOT_INCLUDE_BASE64_DEFAULT", True)
MAX_ERROR_RETRY_ATTEMPTS = 1
SWAGGER_EXAMPLE_CONSULTAS = [
    "A DILA DA SILVA BRITO LIMA",
    "BA N TCHI OLIVE CONFORTE N DAH KOUAGOU",
    "CAA SANTOS BARROS MACHADO",
    "D ANGELA ALVES DE BARROS FELIPE",
    "E DILA LARISSA RODRIGUES BERTOLDO",
    "F MAGNIFICAT ZINSOU",
    "GAABI OLIVEIRA DE MESQUITA",
    "HA MOHAMMAD OLIUR RAHMAN",
    "HAABE OLIVEIRA DA SILVA",
    "I DINA APARECIDA DA SILVA GARCIA",
    "J QUECEMIRA BATISTA DOS SANTOS",
    "K TIANA MARLEN SILVA ARAUJO",
]
SWAGGER_EXAMPLE_CPF = "04031769644"
SWAGGER_EXAMPLE_LOTE_4 = [
    "GAABI OLIVEIRA DE MESQUITA",
    "HAABE OLIVEIRA DA SILVA",
    "D ANGELA ALVES DE BARROS FELIPE",
    "I DINA APARECIDA DA SILVA GARCIA",
]


class ItemConsultaSerializer(serializers.Serializer):
    consulta = serializers.CharField(help_text="CPF, NIS ou nome completo.")
    refinar_busca = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Quando true, aplica o filtro 'Beneficiário de Programa Social'.",
    )


def _resolve_refine_flag(payload: Dict[str, Any], default: bool = False) -> bool:
    raw = payload.get("refinar_busca", default)
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off", ""}:
            return False
        return default
    return bool(raw)


def _resolve_include_base64_flag(payload: Dict[str, Any], default: bool = DEFAULT_INCLUDE_BASE64) -> bool:
    raw = payload.get("incluir_base64", default)
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in {"1", "true", "yes", "on"}:
            return True
        if v in {"0", "false", "no", "off", ""}:
            return False
        return default
    return bool(raw)


def _run_single(consulta_param: str, refine_param: bool, incluir_base64: bool) -> Dict[str, Any]:
    from bot.engine.scraper import TransparencyBotAsync

    bot = TransparencyBotAsync(headless=True, alvo=str(consulta_param), usar_refine=bool(refine_param))
    resultado = async_to_sync(bot.run_async)()
    if not incluir_base64:
        resultado = remover_imagens_base64(resultado)
    return resultado


def _run_batch(itens: List[Dict[str, Any]], incluir_base64: bool) -> Dict[str, Any]:
    max_browsers, max_consultas_por_browser = get_runtime_limits()
    return async_to_sync(executar_consultas_em_lote_async)(
        itens,
        headless=True,
        max_consultas_por_browser=max_consultas_por_browser,
        incluir_base64=incluir_base64,
    )


def _json_error(message: str, status_code: int) -> JsonResponse:
    return JsonResponse({"status": "error", "error": message}, status=status_code)


def _status_from_result(res: Dict[str, Any]) -> str:
    if res.get("status") == "invalid":
        return "invalid"
    if res.get("status") == "error":
        return "error"
    if res.get("status") == "not_found":
        return "not_found"
    return "ok"


def _should_retry_result(res: Dict[str, Any]) -> bool:
    return _status_from_result(res) == "error"


def _ensure_result_meta(res: Dict[str, Any]) -> Dict[str, Any]:
    meta = res.get("meta")
    if isinstance(meta, dict):
        return meta
    meta = {}
    res["meta"] = meta
    return meta


def _annotate_result_retry_meta(
    res: Dict[str, Any],
    *,
    tentativas_execucao: int,
    retry_acionado: bool,
    recuperado_por_retry: bool,
    status_primeira_tentativa: str,
) -> Dict[str, Any]:
    meta = _ensure_result_meta(res)
    meta["retry"] = {
        "tentativas_execucao": max(1, int(tentativas_execucao)),
        "retry_acionado": bool(retry_acionado),
        "recuperado_por_retry": bool(recuperado_por_retry),
        "status_primeira_tentativa": str(status_primeira_tentativa or "unknown"),
        "status_final": _status_from_result(res),
    }
    return res


def _result_retry_meta(res: Dict[str, Any]) -> Dict[str, Any]:
    meta = res.get("meta")
    if not isinstance(meta, dict):
        return {}
    retry = meta.get("retry")
    if isinstance(retry, dict):
        return retry
    return {}


def _annotate_batch_item_retry_meta(
    item: Dict[str, Any],
    *,
    tentativas_execucao: int,
    retry_acionado: bool,
    recuperado_por_retry: bool,
    status_primeira_tentativa: str,
) -> Dict[str, Any]:
    resultado = item.get("resultado")
    if isinstance(resultado, dict):
        _annotate_result_retry_meta(
            resultado,
            tentativas_execucao=tentativas_execucao,
            retry_acionado=retry_acionado,
            recuperado_por_retry=recuperado_por_retry,
            status_primeira_tentativa=status_primeira_tentativa,
        )
    return item


def _default_batch_retry_summary() -> Dict[str, Any]:
    return {
        "itens_com_retry": 0,
        "itens_recuperados": 0,
        "itens_erro_final": 0,
        "indices_entrada_retentados": [],
    }


def _attach_batch_retry_summary(saida_execucao: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
    meta_execucao = dict(saida_execucao.get("meta_execucao") or {})
    meta_execucao["retry"] = summary
    saida_execucao["meta_execucao"] = meta_execucao
    return saida_execucao


def _run_single_with_retry(consulta_param: str, refine_param: bool, incluir_base64: bool) -> Dict[str, Any]:
    resultado = _run_single(consulta_param, refine_param, incluir_base64)
    status_primeira_tentativa = _status_from_result(resultado)
    if MAX_ERROR_RETRY_ATTEMPTS < 1 or not _should_retry_result(resultado):
        return _annotate_result_retry_meta(
            resultado,
            tentativas_execucao=1,
            retry_acionado=False,
            recuperado_por_retry=False,
            status_primeira_tentativa=status_primeira_tentativa,
        )

    log_event(
        logger,
        logging.INFO,
        "api_consulta_retry_acionado",
        consulta=mascarar_identificador(str(consulta_param)),
        refinar_busca=bool(refine_param),
        status_primeira_tentativa=status_primeira_tentativa,
        tentativa_extra=1,
    )

    try:
        resultado_retry = _run_single(consulta_param, refine_param, incluir_base64)
    except Exception:
        logger.exception("Falha na tentativa unica de retry da consulta %s", consulta_param)
        return _annotate_result_retry_meta(
            resultado,
            tentativas_execucao=2,
            retry_acionado=True,
            recuperado_por_retry=False,
            status_primeira_tentativa=status_primeira_tentativa,
        )

    status_final = _status_from_result(resultado_retry)
    recuperado_por_retry = status_final != "error"
    _annotate_result_retry_meta(
        resultado_retry,
        tentativas_execucao=2,
        retry_acionado=True,
        recuperado_por_retry=recuperado_por_retry,
        status_primeira_tentativa=status_primeira_tentativa,
    )
    log_event(
        logger,
        logging.INFO,
        "api_consulta_retry_finalizado",
        consulta=mascarar_identificador(str(consulta_param)),
        refinar_busca=bool(refine_param),
        status_primeira_tentativa=status_primeira_tentativa,
        status_final=status_final,
        recuperado_por_retry=recuperado_por_retry,
    )
    return resultado_retry


def _batch_item_has_error(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    resultado = item.get("resultado")
    return isinstance(resultado, dict) and _should_retry_result(resultado)


def _merge_batch_retry_results(
    saida_inicial: Dict[str, Any],
    saida_retry: Dict[str, Any],
) -> Dict[str, Any]:
    retry_por_indice: Dict[int, Dict[str, Any]] = {}
    for item in saida_retry.get("resultados", []):
        if not isinstance(item, dict):
            continue
        idx = int(item.get("indice_entrada", -1))
        if idx >= 0:
            retry_por_indice[idx] = item

    resultados_mesclados: List[Dict[str, Any]] = []
    for item in saida_inicial.get("resultados", []):
        if not isinstance(item, dict):
            resultados_mesclados.append(item)
            continue

        idx = int(item.get("indice_entrada", -1))
        retry_item = retry_por_indice.get(idx)
        if retry_item is None:
            resultados_mesclados.append(item)
            continue

        mesclado = dict(retry_item)
        mesclado["duracao_segundos"] = max(
            0.0,
            float(item.get("duracao_segundos", 0.0)) + float(retry_item.get("duracao_segundos", 0.0)),
        )
        resultados_mesclados.append(mesclado)

    saida_final = dict(saida_inicial)
    saida_final["resultados"] = resultados_mesclados
    return saida_final


def _run_batch_with_retry(itens: List[Dict[str, Any]], incluir_base64: bool) -> Dict[str, Any]:
    saida_execucao = _run_batch(itens, incluir_base64=incluir_base64)
    for item in saida_execucao.get("resultados", []):
        if not isinstance(item, dict):
            continue
        resultado = item.get("resultado")
        if not isinstance(resultado, dict):
            continue
        _annotate_batch_item_retry_meta(
            item,
            tentativas_execucao=1,
            retry_acionado=False,
            recuperado_por_retry=False,
            status_primeira_tentativa=_status_from_result(resultado),
        )

    if MAX_ERROR_RETRY_ATTEMPTS < 1:
        return _attach_batch_retry_summary(saida_execucao, _default_batch_retry_summary())

    retry_itens: List[Dict[str, Any]] = []
    retry_indices: set[int] = set()
    status_inicial_por_indice: Dict[int, str] = {}
    for item in saida_execucao.get("resultados", []):
        if not _batch_item_has_error(item):
            continue
        idx = int(item.get("indice_entrada", -1))
        if idx < 0 or idx >= len(itens) or idx in retry_indices:
            continue
        retry_indices.add(idx)
        retry_itens.append(itens[idx])
        resultado = item.get("resultado")
        if isinstance(resultado, dict):
            status_inicial_por_indice[idx] = _status_from_result(resultado)

    if not retry_itens:
        return _attach_batch_retry_summary(saida_execucao, _default_batch_retry_summary())

    log_event(
        logger,
        logging.INFO,
        "api_batch_retry_acionado",
        total_itens=len(retry_itens),
        indices_entrada=sorted(retry_indices),
        consultas=[mascarar_identificador(str(item.get("consulta"))) for item in retry_itens],
        refinar_busca=[bool(item.get("refinar_busca", False)) for item in retry_itens],
    )

    try:
        saida_retry = _run_batch(retry_itens, incluir_base64=incluir_base64)
    except Exception:
        logger.exception("Falha na tentativa unica de retry do lote")
        summary = {
            "itens_com_retry": len(retry_itens),
            "itens_recuperados": 0,
            "itens_erro_final": len(retry_itens),
            "indices_entrada_retentados": sorted(retry_indices),
        }
        for item in saida_execucao.get("resultados", []):
            if not isinstance(item, dict):
                continue
            idx = int(item.get("indice_entrada", -1))
            if idx not in retry_indices:
                continue
            _annotate_batch_item_retry_meta(
                item,
                tentativas_execucao=2,
                retry_acionado=True,
                recuperado_por_retry=False,
                status_primeira_tentativa=status_inicial_por_indice.get(idx, "error"),
            )
        return _attach_batch_retry_summary(saida_execucao, summary)

    saida_final = _merge_batch_retry_results(saida_execucao, saida_retry)
    summary = {
        "itens_com_retry": len(retry_itens),
        "itens_recuperados": 0,
        "itens_erro_final": 0,
        "indices_entrada_retentados": sorted(retry_indices),
    }
    for item in saida_final.get("resultados", []):
        if not isinstance(item, dict):
            continue
        idx = int(item.get("indice_entrada", -1))
        if idx not in retry_indices:
            continue
        resultado = item.get("resultado")
        status_inicial = status_inicial_por_indice.get(idx, "error")
        status_final = _status_from_result(resultado) if isinstance(resultado, dict) else "error"
        recuperado_por_retry = status_final != "error"
        if recuperado_por_retry:
            summary["itens_recuperados"] += 1
        else:
            summary["itens_erro_final"] += 1
        _annotate_batch_item_retry_meta(
            item,
            tentativas_execucao=2,
            retry_acionado=True,
            recuperado_por_retry=recuperado_por_retry,
            status_primeira_tentativa=status_inicial,
        )
        log_event(
            logger,
            logging.INFO,
            "api_batch_retry_item_finalizado",
            consulta=mascarar_identificador(str(item.get("consulta"))),
            indice_entrada=idx,
            refinar_busca=bool(item.get("refinar_busca", False)),
            status_primeira_tentativa=status_inicial,
            status_final=status_final,
            recuperado_por_retry=recuperado_por_retry,
            id_consulta=(resultado or {}).get("id_consulta", "-") if isinstance(resultado, dict) else "-",
        )
    log_event(
        logger,
        logging.INFO,
        "api_batch_retry_finalizado",
        total_itens=summary["itens_com_retry"],
        itens_recuperados=summary["itens_recuperados"],
        itens_erro_final=summary["itens_erro_final"],
        indices_entrada=summary["indices_entrada_retentados"],
    )
    return _attach_batch_retry_summary(saida_final, summary)


def _single_http_status_from_result(res: Dict[str, Any]) -> int:
    status_item = _status_from_result(res)
    if status_item == "invalid":
        return 400
    if status_item == "error":
        # Erro de execução do bot/dependência externa (Portal da Transparência)
        return 502
    return 200


def _batch_http_status(resultados: List[Dict[str, Any]]) -> int:
    statuses = [str(item.get("status") or "").lower() for item in resultados if isinstance(item, dict)]
    has_error = any(s == "error" for s in statuses)
    has_invalid = any(s == "invalid" for s in statuses)
    has_ok = any(s in {"ok", "not_found"} for s in statuses)

    if has_error and not has_ok and not has_invalid:
        return 502
    if has_invalid and not has_ok and not has_error:
        return 400
    if has_error or has_invalid:
        return 207
    return 200


def _observe_item_metrics(mode: str, status_item: str, elapsed_seconds: float) -> None:
    status_norm = str(status_item or "unknown").lower()
    API_CONSULTA_ITEM_DURATION_SECONDS.labels(mode=mode, status=status_norm).observe(max(0.0, elapsed_seconds))
    API_CONSULTA_ITEM_STATUS_TOTAL.labels(mode=mode, status=status_norm).inc()
    API_CONSULTA_RESULT_KIND_TOTAL.labels(mode=mode, kind=classify_result_kind(status_norm)).inc()


@extend_schema(
    methods=['POST'],
    tags=["Consulta"],
    summary="Executa consulta no Portal da Transparência (única ou lote)",
    description=(
        "Suporta payload unitário (`consulta`) e em lote (`consultas`, 1..N), "
        "com `refinar_busca` e `incluir_base64` opcionais.\n\n"
        "Autenticação obrigatória por requisição: cada token Bearer é de uso único "
        "(a cada consulta, gere um novo token em `/api/token/`).\n\n"
        "Paralelismo padrão: 1 browser, até 4 consultas por abas em paralelo. "
        "Quando excede essa capacidade, os blocos entram em fila interna (sem rejeição por tamanho apenas por volume).\n\n"
        "Há exemplos de lote de 4 consultas e lote gigante de 12 consultas sem evidências Base64.\n\n"
        "Campos aceitos em 'consulta': CPF (11 dígitos), NIS (11 dígitos) ou nome completo.\n"
        "Use `incluir_base64=false` para remover evidências/imagens da resposta.\n"
        "Resposta do bot sempre inclui `id_consulta` (UUID) e `data_hora_consulta` "
        "em todas as execuções para auditoria.\n"
        "Quando não houver dados cadastrais, `pessoa.nome`, `pessoa.cpf` e `pessoa.localidade` retornam `N/A`."
    ),
    examples=[
        OpenApiExample(
            "Consulta unitária simples (CPF)",
            value={"consulta": SWAGGER_EXAMPLE_CPF, "refinar_busca": False},
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Consulta unitária simples (nome)",
            value={"consulta": SWAGGER_EXAMPLE_LOTE_4[0], "refinar_busca": False},
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Consulta em lote simples (4 itens)",
            value={
                "consultas": SWAGGER_EXAMPLE_LOTE_4,
                "refinar_busca": False,
            },
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Consulta unitária avançada",
            value={"consulta": SWAGGER_EXAMPLE_LOTE_4[0], "refinar_busca": True},
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Consulta em lote avançada (4 itens)",
            value={
                "consultas": SWAGGER_EXAMPLE_LOTE_4,
                "refinar_busca": True,
            },
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Consulta em lote gigante (12 itens, sem evidências Base64)",
            value={
                "consultas": SWAGGER_EXAMPLE_CONSULTAS,
                "refinar_busca": True,
                "incluir_base64": False,
            },
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Consulta leve (sem evidências Base64)",
            value={
                "consulta": "HAABE OLIVEIRA DA SILVA",
                "refinar_busca": True,
                "incluir_base64": False,
            },
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Resposta: sucesso",
            value={
                "id_consulta": "6a7e35d0-6d19-4e53-8b02-17bb30a8b7f6",
                "data_hora_consulta": "15/03/2026 12:45",
                "pessoa": {
                    "consulta": SWAGGER_EXAMPLE_CONSULTAS[0],
                    "nome": "NOME DA PESSOA",
                    "cpf": "***.***.***-**",
                    "localidade": "UF",
                    "quantidade_beneficios": 1,
                },
                "beneficios": [],
                "meta": {
                    "id_consulta": "6a7e35d0-6d19-4e53-8b02-17bb30a8b7f6",
                    "data_hora_consulta": "15/03/2026 12:45",
                    "resultados_encontrados": 1,
                    "beneficios_encontrados": ["Auxílio Brasil"],
                    "panorama_relacao": "<base64>",
                },
            },
            response_only=True,
            status_codes=["200"],
            media_type='application/json',
        ),
        OpenApiExample(
            "Resposta: sem resultado (não encontrado)",
            value={
                "id_consulta": "67df0b30-d289-4f91-9ff3-1577ec67b4b3",
                "data_hora_consulta": "15/03/2026 12:46",
                "status": "not_found",
                "pessoa": {
                    "consulta": SWAGGER_EXAMPLE_CONSULTAS[6],
                    "nome": "N/A",
                    "cpf": "N/A",
                    "localidade": "N/A",
                },
                "beneficios": [],
                "meta": {
                    "id_consulta": "67df0b30-d289-4f91-9ff3-1577ec67b4b3",
                    "data_hora_consulta": "15/03/2026 12:46",
                    "resultados_encontrados": 0,
                    "evidencia_resultados_zero": "<base64>",
                    "mensagem": "Não foi possível retornar os dados no tempo de resposta solicitado",
                },
            },
            response_only=True,
            status_codes=["200"],
            media_type='application/json',
        ),
    ],
    request=inline_serializer(
        name="ConsultaRequest",
        fields={
            "consulta": serializers.CharField(required=False, help_text="Consulta única: CPF, NIS ou nome."),
            "consultas": serializers.ListField(
                child=serializers.CharField(),
                required=False,
                help_text="Lote simples: lista de consultas (processadas com fila interna quando exceder capacidade paralela).",
            ),
            "itens": ItemConsultaSerializer(many=True, required=False),
            "refinar_busca": serializers.BooleanField(
                required=False,
                default=False,
                help_text="Ativa o filtro 'Beneficiário de Programa Social'.",
            ),
            "incluir_base64": serializers.BooleanField(
                required=False,
                default=DEFAULT_INCLUDE_BASE64,
                help_text="Quando false, remove evidências/imagens Base64 do retorno.",
            ),
        },
    ),
    responses=OpenApiTypes.OBJECT,
)
@api_view(['POST'])
def consulta(request: Request):
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return JsonResponse({"status": "error", "error": "Missing bearer token"}, status=401)
    token = auth_header.replace("Bearer ", "", 1).strip()
    valid, claims = validate_token(token)
    if not valid:
        return JsonResponse({"status": "error", "error": "Invalid or expired token"}, status=401)
    if not scope_allows(claims, ["bot:read"]):
        return JsonResponse({"status": "error", "error": "Insufficient scope"}, status=403)
    if not consume_token_once(claims):
        return JsonResponse({"status": "error", "error": "Invalid or expired token"}, status=401)

    payload = request.data if isinstance(request.data, dict) else {}
    incluir_base64 = _resolve_include_base64_flag(payload, default=DEFAULT_INCLUDE_BASE64)

    resultados: List[Dict[str, Any]] = []

    if 'consultas' in payload and isinstance(payload.get('consultas'), list):
        request_start = time.monotonic()
        mode = "batch_consultas"
        consultas = payload.get('consultas', [])
        refine_default = _resolve_refine_flag(payload, default=False)
        max_browsers, max_consultas_por_browser = get_runtime_limits()
        API_CONSULTA_REQUESTS_TOTAL.labels(mode=mode).inc()
        if len(consultas) == 0:
            return _json_error('Lista "consultas" vazia', 400)
        API_CONSULTA_BATCH_SIZE.observe(len(consultas))
        log_event(
            logger,
            logging.INFO,
            "api_batch_consultas_recebida",
            consultas=[mascarar_identificador(str(c)) for c in consultas],
            refine_default=refine_default,
            incluir_base64=incluir_base64,
            max_browsers=max_browsers,
            max_consultas_por_browser=max_consultas_por_browser,
        )
        itens_execucao = [
            {"indice_entrada": idx, "consulta": str(c), "refinar_busca": refine_default}
            for idx, c in enumerate(consultas)
        ]
        saida_execucao = _run_batch_with_retry(itens_execucao, incluir_base64=incluir_base64)
        resultados = [None] * len(consultas)
        for item in saida_execucao.get("resultados", []):
            idx = int(item.get("indice_entrada", -1))
            if idx < 0 or idx >= len(consultas):
                continue
            c = consultas[idx]
            res = item.get("resultado") or {"status": "error", "error": "Resultado ausente"}
            status_item = _status_from_result(res)
            retry_meta = _result_retry_meta(res)
            _observe_item_metrics(mode=mode, status_item=status_item, elapsed_seconds=float(item.get("duracao_segundos", 0.0)))
            log_event(
                logger,
                logging.INFO,
                "api_batch_item_processado",
                consulta=mascarar_identificador(str(c)),
                status=status_item,
                id_consulta=res.get("id_consulta", "-"),
                tentativas_execucao=retry_meta.get("tentativas_execucao", 1),
                retry_acionado=retry_meta.get("retry_acionado", False),
                recuperado_por_retry=retry_meta.get("recuperado_por_retry", False),
            )
            resultados[idx] = {"consulta": c, "status": status_item, "resultado": res}
        for idx, item in enumerate(resultados):
            if item is None:
                _observe_item_metrics(mode=mode, status_item="error", elapsed_seconds=0.0)
                resultados[idx] = {"consulta": consultas[idx], "status": "error", "error": "Resultado ausente"}

        API_CONSULTA_DURATION_SECONDS.labels(mode=mode).observe(max(0.0, time.monotonic() - request_start))
        return JsonResponse(
            {"resultados": resultados, "meta_execucao": saida_execucao.get("meta_execucao", {})},
            safe=False,
            status=_batch_http_status(resultados),
        )

    if 'itens' in payload and isinstance(payload.get('itens'), list):
        request_start = time.monotonic()
        mode = "batch_itens"
        itens = payload.get('itens', [])
        max_browsers, max_consultas_por_browser = get_runtime_limits()
        API_CONSULTA_REQUESTS_TOTAL.labels(mode=mode).inc()
        if len(itens) == 0:
            return _json_error('Lista "itens" vazia', 400)
        API_CONSULTA_BATCH_SIZE.observe(len(itens))
        log_event(
            logger,
            logging.INFO,
            "api_batch_itens_recebida",
            consultas=[mascarar_identificador(str(i.get('consulta') or i.get('alvo'))) for i in itens],
            incluir_base64=incluir_base64,
            max_browsers=max_browsers,
            max_consultas_por_browser=max_consultas_por_browser,
        )
        resultados = [None] * len(itens)
        itens_execucao: List[Dict[str, Any]] = []
        for idx, item in enumerate(itens):
            c = item.get('consulta') or item.get('alvo')
            refinar_busca = _resolve_refine_flag(item, default=False)
            if not c:
                _observe_item_metrics(mode=mode, status_item="error", elapsed_seconds=0.0)
                resultados[idx] = {"consulta": None, "status": "error", "error": 'Campo "consulta" ausente no item'}
                continue
            itens_execucao.append(
                {
                    "indice_entrada": idx,
                    "consulta": str(c),
                    "refinar_busca": refinar_busca,
                }
            )

        saida_execucao = {"resultados": [], "meta_execucao": {}}
        if itens_execucao:
            saida_execucao = _run_batch_with_retry(itens_execucao, incluir_base64=incluir_base64)

        for item in saida_execucao.get("resultados", []):
            idx = int(item.get("indice_entrada", -1))
            if idx < 0 or idx >= len(itens):
                continue
            c = itens[idx].get("consulta") or itens[idx].get("alvo")
            res = item.get("resultado") or {"status": "error", "error": "Resultado ausente"}
            status_item = _status_from_result(res)
            retry_meta = _result_retry_meta(res)
            _observe_item_metrics(mode=mode, status_item=status_item, elapsed_seconds=float(item.get("duracao_segundos", 0.0)))
            log_event(
                logger,
                logging.INFO,
                "api_item_processado",
                consulta=mascarar_identificador(str(c)),
                status=status_item,
                id_consulta=res.get("id_consulta", "-"),
                tentativas_execucao=retry_meta.get("tentativas_execucao", 1),
                retry_acionado=retry_meta.get("retry_acionado", False),
                recuperado_por_retry=retry_meta.get("recuperado_por_retry", False),
            )
            resultados[idx] = {"consulta": c, "status": status_item, "resultado": res}

        for idx, item in enumerate(resultados):
            if item is None:
                _observe_item_metrics(mode=mode, status_item="error", elapsed_seconds=0.0)
                c = itens[idx].get("consulta") or itens[idx].get("alvo")
                resultados[idx] = {"consulta": c, "status": "error", "error": "Resultado ausente"}

        API_CONSULTA_DURATION_SECONDS.labels(mode=mode).observe(max(0.0, time.monotonic() - request_start))
        return JsonResponse(
            {"resultados": resultados, "meta_execucao": saida_execucao.get("meta_execucao", {})},
            safe=False,
            status=_batch_http_status(resultados),
        )

    # Single
    request_start = time.monotonic()
    mode = "single"
    API_CONSULTA_REQUESTS_TOTAL.labels(mode=mode).inc()

    consulta_param = payload.get('consulta') or payload.get('alvo')
    refine_param = _resolve_refine_flag(payload, default=False)

    if consulta_param is None:
        return _json_error('Parâmetro "consulta" não informado', 400)

    log_event(
        logger,
        logging.INFO,
        "api_consulta_recebida",
        consulta=mascarar_identificador(str(consulta_param)),
        refinar_busca=refine_param,
        incluir_base64=incluir_base64,
    )
    try:
        item_start = time.monotonic()
        resultado = _run_single_with_retry(consulta_param, refine_param, incluir_base64)
        status_item = _status_from_result(resultado)
        retry_meta = _result_retry_meta(resultado)
        _observe_item_metrics(mode=mode, status_item=status_item, elapsed_seconds=time.monotonic() - item_start)
        log_event(
            logger,
            logging.INFO,
            "api_consulta_processada",
            consulta=mascarar_identificador(str(consulta_param)),
            status=status_item,
            id_consulta=resultado.get("id_consulta", "-"),
            tentativas_execucao=retry_meta.get("tentativas_execucao", 1),
            retry_acionado=retry_meta.get("retry_acionado", False),
            recuperado_por_retry=retry_meta.get("recuperado_por_retry", False),
        )
        API_CONSULTA_DURATION_SECONDS.labels(mode=mode).observe(max(0.0, time.monotonic() - request_start))
        return JsonResponse(resultado, safe=False, status=_single_http_status_from_result(resultado))
    except Exception as e:
        logger.exception("Erro processando consulta unica %s", consulta_param)
        _observe_item_metrics(mode=mode, status_item="error", elapsed_seconds=time.monotonic() - request_start)
        API_CONSULTA_DURATION_SECONDS.labels(mode=mode).observe(max(0.0, time.monotonic() - request_start))
        return JsonResponse({"status": "error", "error": str(e)}, status=500)


@extend_schema(
    methods=['POST'],
    tags=["Autenticação"],
    summary="Gerar token de acesso (OAuth2 client_credentials, uso único)",
    description=(
        "Envie grant_type=client_credentials, client_id e client_secret para receber um JWT HS256. "
        "Cada token pode ser usado uma única vez no endpoint `/api/consulta/`."
    ),
    examples=[
        OpenApiExample(
            'Requisição de token',
            value={"grant_type": "client_credentials", "client_id": "CLIENT_ID", "client_secret": "CLIENT_SECRET"},
            request_only=True,
            media_type='application/json',
        ),
    ],
    request=inline_serializer(
        name="TokenRequest",
        fields={
            "grant_type": serializers.CharField(help_text="Use sempre client_credentials."),
            "client_id": serializers.CharField(),
            "client_secret": serializers.CharField(),
            "scope": serializers.CharField(required=False, default="bot:read"),
        },
    ),
    responses=inline_serializer(
        name="TokenResponse",
        fields={
            "access_token": serializers.CharField(),
            "expires_in": serializers.IntegerField(),
            "token_type": serializers.CharField(),
            "scope": serializers.CharField(),
        },
    ),
    auth=[],
)
@api_view(['POST'])
def token(request: Request):
    """
    Fluxo client_credentials: devolve access_token de uso único.
    """
    data = request.data if isinstance(request.data, dict) else {}
    grant_type = data.get("grant_type")
    client_id = data.get("client_id")
    client_secret = data.get("client_secret")
    scope = data.get("scope", "bot:read")

    from django.conf import settings as dj_settings

    if grant_type != "client_credentials":
        return _json_error('Parâmetro "grant_type" ausente ou inválido (use client_credentials)', 400)

    if not client_id or not client_secret:
        return _json_error('Parâmetros "client_id" e "client_secret" são obrigatórios', 400)

    expected_id = getattr(dj_settings, "OAUTH_CLIENT_ID", None)
    expected_secret = getattr(dj_settings, "OAUTH_CLIENT_SECRET", None)
    if not expected_id or not expected_secret:
        return _json_error("Cliente OAuth não configurado", 500)

    if client_id != expected_id or client_secret != expected_secret:
        return _json_error("Credenciais do cliente inválidas", 401)

    requested_scopes = str(scope or "").split()
    allowed_scopes = {"bot:read"}
    if not requested_scopes:
        return _json_error('Parâmetro "scope" inválido', 400)
    if not all(s in allowed_scopes for s in requested_scopes):
        return _json_error('Parâmetro "scope" inválido', 400)

    ttl = getattr(dj_settings, "API_TOKEN_TTL", 600)
    token_value, exp = issue_token(client_id, ttl, scope, dj_settings.OAUTH_AUDIENCE)
    return JsonResponse({"access_token": token_value, "expires_in": ttl, "token_type": "Bearer", "scope": scope})
