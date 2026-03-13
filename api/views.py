import json
import logging
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from bot.scraper import TransparencyBot

logger = logging.getLogger(__name__)


import json
import logging
from typing import List, Dict, Any
from django.http import JsonResponse, HttpResponseBadRequest

from rest_framework.decorators import api_view
from rest_framework.request import Request

from bot.scraper import TransparencyBot

from drf_spectacular.utils import extend_schema, OpenApiExample
from drf_spectacular.types import OpenApiTypes

logger = logging.getLogger(__name__)


def _run_single(consulta_param: str, refine_param: bool) -> Dict[str, Any]:
    bot = TransparencyBot(headless=True)
    bot.alvo = str(consulta_param)
    bot.usar_refine = bool(refine_param)
    resultado = bot.run()
    return resultado


@extend_schema(
    methods=['POST'],
    description=(
        'Executa a consulta no TransparencyBot. Suporta 3 formatos de payload:\n'
        '- Single: {"consulta":"...","refine":false}\n'
        '- Batch simples: {"consultas":["...","..."],"refine":false}\n'
        '- Batch avançado: {"itens":[{"consulta":"...","refine":false}, ...]}'
    ),
    examples=[
        OpenApiExample('Single', value={"consulta": "04031769644", "refine": False}, request_only=True, media_type='application/json'),
        OpenApiExample('Batch simples', value={"consultas": ["04031769644", "12345678901"], "refine": False}, request_only=True, media_type='application/json'),
        OpenApiExample('Batch avançado', value={"itens": [{"consulta": "04031769644", "refine": False}, {"consulta": "12345678901", "refine": True}]}, request_only=True, media_type='application/json'),
    ],
    request=OpenApiTypes.OBJECT,
    responses=OpenApiTypes.OBJECT,
)
@api_view(['POST'])
def consulta(request: Request):
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
        logger.info(f"API chamada (batch consultas): {consultas} refine_default={refine_default}")
        for c in consultas:
            try:
                res = _run_single(c, refine_default)
                resultados.append({"consulta": c, "status": "ok", "resultado": res})
            except Exception as e:
                logger.exception("Erro processando consulta %s", c)
                resultados.append({"consulta": c, "status": "error", "error": str(e)})

        return JsonResponse({"resultados": resultados}, safe=False)

    if 'itens' in payload and isinstance(payload.get('itens'), list):
        itens = payload.get('itens', [])
        logger.info(f"API chamada (itens): {itens}")
        for item in itens:
            c = item.get('consulta') or item.get('alvo')
            refine = item.get('refine', False)
            if not c:
                resultados.append({"consulta": None, "status": "error", "error": 'Missing consulta in item'})
                continue
            try:
                res = _run_single(c, refine)
                resultados.append({"consulta": c, "status": "ok", "resultado": res})
            except Exception as e:
                logger.exception("Erro processando item %s", c)
                resultados.append({"consulta": c, "status": "error", "error": str(e)})

        return JsonResponse({"resultados": resultados}, safe=False)

    # Single
    consulta_param = payload.get('consulta') or payload.get('alvo')
    refine_param = payload.get('refine', False)

    if consulta_param is None:
        return HttpResponseBadRequest('Missing "consulta" parameter')

    logger.info(f"API chamada: consulta={consulta_param} refine={refine_param}")
    try:
        resultado = _run_single(consulta_param, refine_param)
        return JsonResponse(resultado, safe=False)
    except Exception as e:
        logger.exception("Erro processando consulta unica %s", consulta_param)
        return JsonResponse({"status": "error", "error": str(e)}, status=500)
