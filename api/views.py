import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.http import JsonResponse, HttpResponseBadRequest
from rest_framework.decorators import api_view
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from bot.scraper import TransparencyBot
from bot.validators import mascarar_identificador
from .auth import issue_token, validate_token, scope_allows

logger = logging.getLogger(__name__)

MAX_BATCH = 3
MAX_WORKERS = 3


def _run_single(consulta_param: str, refine_param: bool) -> Dict[str, Any]:
    bot = TransparencyBot(headless=True, alvo=str(consulta_param), usar_refine=bool(refine_param))
    resultado = bot.run()
    return resultado


@extend_schema(
    methods=['POST'],
    tags=["Consulta"],
    summary="Executa a consulta no Portal da Transparência (single ou batch)",
    description=(
        "Suporta 3 formatos de payload:\n"
        "- Single: {\"consulta\":\"...\",\"refine\":false}\n"
        "- Batch simples: {\"consultas\":[\"...\",\"...\"],\"refine\":false} (máx. 3)\n"
        "- Batch avançado: {\"itens\":[{\"consulta\":\"...\",\"refine\":false}, ...]} (máx. 3, refine opcional por item)\n\n"
        "Campos aceitos em 'consulta': CPF (11 dígitos), NIS (11 dígitos) ou nome. "
        "Se 'refine' for omitido no item, usa False por padrão."
    ),
    examples=[
        OpenApiExample('Single', value={"consulta": "04031769644", "refine": False}, request_only=True, media_type='application/json'),
        OpenApiExample('Batch simples', value={"consultas": ["04031769644", "12345678901"], "refine": True}, request_only=True, media_type='application/json'),
        OpenApiExample('Batch avançado', value={"itens": [{"consulta": "04031769644"}, {"consulta": "12345678901", "refine": False}]}, request_only=True, media_type='application/json'),
    ],
    request=OpenApiTypes.OBJECT,
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
        refine_default = bool(payload.get('refine', False))
        if len(consultas) == 0:
            return HttpResponseBadRequest('Lista "consultas" vazia')
        if len(consultas) > MAX_BATCH:
            return JsonResponse({"status": "error", "error": f"Máximo de {MAX_BATCH} consultas por requisição"}, status=400)
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
                    status_item = "ok" if res.get("status") != "invalid" else "invalid"
                    resultados[idx] = {"consulta": c, "status": status_item, "resultado": res}
                except Exception as e:
                    logger.exception("Erro processando consulta %s", c)
                    resultados[idx] = {"consulta": c, "status": "error", "error": str(e)}

        return JsonResponse({"resultados": resultados}, safe=False)

    if 'itens' in payload and isinstance(payload.get('itens'), list):
        itens = payload.get('itens', [])
        if len(itens) == 0:
            return HttpResponseBadRequest('Lista "itens" vazia')
        if len(itens) > MAX_BATCH:
            return JsonResponse({"status": "error", "error": f"Máximo de {MAX_BATCH} itens por requisição"}, status=400)
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
                refine = item.get('refine', False)
                ordered_inputs.append((c, refine))
                if not c:
                    resultados.append({"consulta": None, "status": "error", "error": 'Missing consulta in item'})
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
                    status_item = "ok" if res.get("status") != "invalid" else "invalid"
                    resultados[idx] = {"consulta": c, "status": status_item, "resultado": res}
                except Exception as e:
                    logger.exception("Erro processando item %s", c)
                    resultados[idx] = {"consulta": c, "status": "error", "error": str(e)}

        return JsonResponse({"resultados": resultados}, safe=False)

    # Single
    consulta_param = payload.get('consulta') or payload.get('alvo')
    refine_param = payload.get('refine', False)

    if consulta_param is None:
        return HttpResponseBadRequest('Missing "consulta" parameter')

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
    tags=["Auth"],
    summary="OAuth2 client_credentials (gera JWT HS256)",
    description="Envie grant_type=client_credentials, client_id/client_secret (do .env) e receba um JWT HS256 com scope e audience definidos.",
    examples=[
        OpenApiExample('Token request', value={"grant_type": "client_credentials", "client_id": "CLIENT_ID", "client_secret": "CLIENT_SECRET"}, request_only=True, media_type='application/json'),
    ],
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
    auth=None,
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
        return HttpResponseBadRequest('Missing or invalid "grant_type" (use client_credentials)')

    if not client_id or not client_secret:
        return HttpResponseBadRequest('Missing "client_id" or "client_secret"')

    expected_id = getattr(dj_settings, "OAUTH_CLIENT_ID", None)
    expected_secret = getattr(dj_settings, "OAUTH_CLIENT_SECRET", None)
    if not expected_id or not expected_secret:
        return JsonResponse({"status": "error", "error": "OAuth client not configured"}, status=500)

    if client_id != expected_id or client_secret != expected_secret:
        return JsonResponse({"status": "error", "error": "Invalid client credentials"}, status=401)

    ttl = getattr(dj_settings, "API_TOKEN_TTL", 600)
    token_value, exp = issue_token(client_id, ttl, scope, dj_settings.OAUTH_AUDIENCE)
    return JsonResponse({"access_token": token_value, "expires_in": ttl, "token_type": "Bearer", "scope": scope})
