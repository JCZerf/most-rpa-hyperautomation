import logging
import os
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework import serializers
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer
from drf_spectacular.types import OpenApiTypes

from bot.scraper import TransparencyBot
from bot.validators import mascarar_identificador
from .auth import issue_token, validate_token, scope_allows

logger = logging.getLogger(__name__)

MAX_BATCH = 3
MAX_WORKERS = max(1, int(os.getenv("BOT_MAX_WORKERS", "1")))


class ItemConsultaSerializer(serializers.Serializer):
    consulta = serializers.CharField(help_text="CPF, NIS ou nome completo.")
    refinar_busca = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Quando true, aplica o filtro 'Beneficiário de Programa Social'.",
    )


def _resolve_refine_flag(payload: Dict[str, Any], default: bool = False) -> bool:
    # Campo preferencial em português. Mantemos 'refine' por compatibilidade retroativa.
    if "refinar_busca" in payload:
        return bool(payload.get("refinar_busca"))
    return bool(payload.get("refine", default))


def _run_single(consulta_param: str, refine_param: bool) -> Dict[str, Any]:
    bot = TransparencyBot(headless=True, alvo=str(consulta_param), usar_refine=bool(refine_param))
    resultado = bot.run()
    return resultado


def _json_error(message: str, status_code: int) -> JsonResponse:
    return JsonResponse({"status": "error", "error": message}, status=status_code)


def _status_from_result(res: Dict[str, Any]) -> str:
    if res.get("status") == "invalid":
        return "invalid"
    if res.get("status") == "error":
        return "error"
    return "ok"


@extend_schema(
    methods=['POST'],
    tags=["Consulta"],
    summary="Executa consulta no Portal da Transparência (única ou lote)",
    description=(
        "Suporta 3 formatos de payload:\n"
        "- Consulta única: {\"consulta\":\"...\",\"refinar_busca\":false}\n"
        "- Lote simples: {\"consultas\":[\"...\",\"...\"],\"refinar_busca\":false} (máx. 3)\n"
        "- Lote avançado: {\"itens\":[{\"consulta\":\"...\",\"refinar_busca\":false}, ...]} (máx. 3)\n\n"
        "Campos aceitos em 'consulta': CPF (11 dígitos), NIS (11 dígitos) ou nome completo.\n"
        "Compatibilidade: o campo legado 'refine' continua aceito."
    ),
    examples=[
        OpenApiExample(
            "Consulta única",
            value={"consulta": "04031769644", "refinar_busca": False},
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Lote simples",
            value={"consultas": ["04031769644", "12345678901"], "refinar_busca": True},
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Lote avançado",
            value={"itens": [{"consulta": "04031769644"}, {"consulta": "12345678901", "refinar_busca": False}]},
            request_only=True,
            media_type='application/json',
        ),
        OpenApiExample(
            "Compatibilidade (legado)",
            value={"consulta": "04031769644", "refine": True},
            request_only=True,
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
                help_text="Lote simples: lista de consultas (máximo 3).",
            ),
            "itens": ItemConsultaSerializer(many=True, required=False),
            "refinar_busca": serializers.BooleanField(
                required=False,
                default=False,
                help_text="Ativa o filtro 'Beneficiário de Programa Social'.",
            ),
            "refine": serializers.BooleanField(
                required=False,
                help_text="Campo legado aceito por compatibilidade.",
            ),
        },
    ),
    responses=OpenApiTypes.OBJECT,
)
@api_view(['POST'])
def consulta(request: Request):
    # Auth: exige Bearer token emitido pelo endpoint /api/token/
    auth_header = request.headers.get("Authorization") or ""
    if not auth_header.startswith("Bearer "):
        return JsonResponse({"status": "error", "error": "Missing bearer token"}, status=401)
    token = auth_header.replace("Bearer ", "", 1).strip()
    valid, claims = validate_token(token)
    if not valid:
        return JsonResponse({"status": "error", "error": "Invalid or expired token"}, status=401)
    if not scope_allows(claims, ["bot:read"]):
        return JsonResponse({"status": "error", "error": "Insufficient scope"}, status=403)

    # request is a DRF Request; use request.data for parsed JSON
    payload = request.data if isinstance(request.data, dict) else {}

    # Detect batch formats
    # 1) { "consultas": ["cpf1","cpf2"], "refine": false }
    # 2) { "itens": [{"consulta": "cpf", "refine": true}, ...] }
    # 3) Single: { "consulta": "cpf", "refine": false }

    resultados: List[Dict[str, Any]] = []

    if 'consultas' in payload and isinstance(payload.get('consultas'), list):
        consultas = payload.get('consultas', [])
        refine_default = _resolve_refine_flag(payload, default=False)
        if len(consultas) == 0:
            return _json_error('Lista "consultas" vazia', 400)
        if len(consultas) > MAX_BATCH:
            return _json_error(f"Máximo de {MAX_BATCH} consultas por requisição", 400)
        logger.info(
            "API chamada (batch consultas): %s refine_default=%s",
            [mascarar_identificador(str(c)) for c in consultas],
            refine_default,
        )
        workers = min(MAX_WORKERS, len(consultas))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(_run_single, c, refine_default): idx for idx, c in enumerate(consultas)}
            resultados = [None] * len(consultas)
            for fut in as_completed(future_map):
                idx = future_map[fut]
                c = consultas[idx]
                try:
                    res = fut.result()
                    status_item = _status_from_result(res)
                    resultados[idx] = {"consulta": c, "status": status_item, "resultado": res}
                except Exception as e:
                    logger.exception("Erro processando consulta %s", c)
                    resultados[idx] = {"consulta": c, "status": "error", "error": str(e)}

        return JsonResponse({"resultados": resultados}, safe=False)

    if 'itens' in payload and isinstance(payload.get('itens'), list):
        itens = payload.get('itens', [])
        if len(itens) == 0:
            return _json_error('Lista "itens" vazia', 400)
        if len(itens) > MAX_BATCH:
            return _json_error(f"Máximo de {MAX_BATCH} itens por requisição", 400)
        logger.info(
            "API chamada (itens): %s",
            [mascarar_identificador(str(i.get('consulta') or i.get('alvo'))) for i in itens],
        )
        workers = min(MAX_WORKERS, len(itens))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {}
            ordered_inputs = []
            for idx, item in enumerate(itens):
                c = item.get('consulta') or item.get('alvo')
                refine = _resolve_refine_flag(item, default=False)
                ordered_inputs.append((c, refine))
                if not c:
                    resultados.append({"consulta": None, "status": "error", "error": 'Campo "consulta" ausente no item'})
                    continue
                future_map[executor.submit(_run_single, c, refine)] = idx

            # prefill results list preserving order
            if resultados:
                # results already has items for missing consulta; ensure length matches
                resultados += [None] * (len(itens) - len(resultados))
            else:
                resultados = [None] * len(itens)

            for fut in as_completed(future_map):
                idx = future_map[fut]
                c, refine = ordered_inputs[idx]
                try:
                    res = fut.result()
                    status_item = _status_from_result(res)
                    resultados[idx] = {"consulta": c, "status": status_item, "resultado": res}
                except Exception as e:
                    logger.exception("Erro processando item %s", c)
                    resultados[idx] = {"consulta": c, "status": "error", "error": str(e)}

        return JsonResponse({"resultados": resultados}, safe=False)

    # Single
    consulta_param = payload.get('consulta') or payload.get('alvo')
    refine_param = _resolve_refine_flag(payload, default=False)

    if consulta_param is None:
        return _json_error('Parâmetro "consulta" não informado', 400)

    logger.info(
        "API chamada: consulta=%s refine=%s",
        mascarar_identificador(str(consulta_param)),
        refine_param,
    )
    try:
        resultado = _run_single(consulta_param, refine_param)
        if resultado.get("status") == "invalid":
            return JsonResponse(resultado, status=400, safe=False)
        return JsonResponse(resultado, safe=False)
    except Exception as e:
        logger.exception("Erro processando consulta unica %s", consulta_param)
        return JsonResponse({"status": "error", "error": str(e)}, status=500)


@extend_schema(
    methods=['POST'],
    tags=["Autenticação"],
    summary="Gerar token de acesso (OAuth2 client_credentials)",
    description="Envie grant_type=client_credentials, client_id e client_secret para receber um JWT HS256.",
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
    Fluxo client_credentials: devolve access_token curto.
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

    ttl = getattr(dj_settings, "API_TOKEN_TTL", 600)
    token_value, exp = issue_token(client_id, ttl, scope, dj_settings.OAUTH_AUDIENCE)
    return JsonResponse({"access_token": token_value, "expires_in": ttl, "token_type": "Bearer", "scope": scope})
