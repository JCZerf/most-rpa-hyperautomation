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
from django.views.decorators.csrf import csrf_exempt

from bot.scraper import TransparencyBot

logger = logging.getLogger(__name__)


def _run_single(consulta_param: str, refine_param: bool) -> Dict[str, Any]:
    bot = TransparencyBot(headless=True)
    bot.alvo = str(consulta_param)
    bot.usar_refine = bool(refine_param)
    resultado = bot.run()
    return resultado


@csrf_exempt
def consulta(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Use POST with JSON body {"consulta": "..., "refine": true|false} or batch formats')

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

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
