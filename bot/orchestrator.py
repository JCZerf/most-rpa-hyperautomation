import asyncio
import logging
import os
import time
from typing import Any, Dict, Iterable, List, Tuple

from .identity import get_random_profile

logger = logging.getLogger(__name__)

IMAGE_PAYLOAD_KEYS = {
    "evidencia_base64",
    "evidencia_resultados_zero",
    "evidencia_sem_beneficio",
    "detalhe_evidencia",
    "panorama_base64",
    "panorama_relacao",
}


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, parsed)


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    return default


def get_runtime_limits(
    max_browsers: int | None = None,
    max_consultas_por_browser: int | None = None,
) -> Tuple[int, int]:
    browsers = max_browsers if max_browsers is not None else _env_int("BOT_MAX_BROWSERS", 2)
    por_browser = (
        max_consultas_por_browser
        if max_consultas_por_browser is not None
        else _env_int("BOT_MAX_CONSULTAS_POR_BROWSER", 4)
    )
    return max(1, int(browsers)), max(1, int(por_browser))


def remover_imagens_base64(valor: Any) -> Any:
    if isinstance(valor, dict):
        novo = {}
        for chave, conteudo in valor.items():
            chave_lower = chave.lower()
            if chave in IMAGE_PAYLOAD_KEYS or "evidencia" in chave_lower or "base64" in chave_lower:
                continue
            novo[chave] = remover_imagens_base64(conteudo)
        return novo
    if isinstance(valor, list):
        return [remover_imagens_base64(item) for item in valor]
    return valor


def _chunked(items: List[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def _executar_consulta_em_aba(
    context: Any,
    item: Dict[str, Any],
    *,
    browser_lote: int,
    ordem_no_browser: int,
    limite_consultas_por_browser: int,
    indice_bloco: int,
    headless: bool,
    incluir_base64: bool,
) -> Dict[str, Any]:
    from .scraper import TransparencyBotAsync

    page = await context.new_page()
    started = time.perf_counter()
    consulta = str(item["consulta"])
    refinar_busca = bool(item.get("refinar_busca", False))

    try:
        bot = TransparencyBotAsync(headless=headless, alvo=consulta, usar_refine=refinar_busca)
        resultado = await bot.run_with_page_async(context, page)
    except Exception as exc:
        logger.exception("Falha não tratada na consulta em aba (consulta=%s)", consulta)
        resultado = {"status": "error", "error": str(exc), "meta": {}}
    finally:
        try:
            await page.close()
        except Exception:
            logger.debug("Falha ao fechar aba da consulta=%s", consulta, exc_info=True)

    if not incluir_base64:
        resultado = remover_imagens_base64(resultado)

    meta = dict(resultado.get("meta") or {})
    meta["browser_lote"] = browser_lote
    meta["ordem_no_browser"] = ordem_no_browser
    meta["limite_consultas_por_browser"] = limite_consultas_por_browser
    meta["indice_bloco_fila"] = indice_bloco + 1
    meta["execucao_paralela_mesmo_browser"] = True
    resultado["meta"] = meta

    return {
        "indice_entrada": int(item["indice_entrada"]),
        "consulta": consulta,
        "refinar_busca": refinar_busca,
        "duracao_segundos": max(0.0, time.perf_counter() - started),
        "resultado": resultado,
    }


async def _executar_bloco_no_browser(
    pw: Any,
    bloco: List[Dict[str, Any]],
    *,
    browser_lote: int,
    indice_bloco: int,
    limite_consultas_por_browser: int,
    headless: bool,
    incluir_base64: bool,
) -> List[Dict[str, Any]]:
    from .browser import create_browser_context_async

    perfil = get_random_profile()
    browser, context, page_inicial = await create_browser_context_async(
        pw,
        headless=headless,
        user_agent=perfil["user_agent"],
        viewport=perfil["viewport"],
        locale=perfil["locale"],
        timezone_id=perfil["timezone_id"],
    )

    try:
        try:
            await page_inicial.close()
        except Exception:
            logger.debug("Falha ao fechar aba inicial do browser_lote=%s", browser_lote, exc_info=True)

        tarefas = []
        for ordem_no_browser, item in enumerate(bloco, start=1):
            tarefas.append(
                asyncio.create_task(
                    _executar_consulta_em_aba(
                        context,
                        item,
                        browser_lote=browser_lote,
                        ordem_no_browser=ordem_no_browser,
                        limite_consultas_por_browser=limite_consultas_por_browser,
                        indice_bloco=indice_bloco,
                        headless=headless,
                        incluir_base64=incluir_base64,
                    )
                )
            )
        return await asyncio.gather(*tarefas)
    finally:
        try:
            await context.close()
        except Exception:
            logger.debug("Falha ao fechar context no browser_lote=%s", browser_lote, exc_info=True)
        try:
            await browser.close()
        except Exception:
            logger.debug("Falha ao fechar browser_lote=%s", browser_lote, exc_info=True)


async def executar_consultas_em_lote_async(
    itens: List[Dict[str, Any]],
    *,
    headless: bool = True,
    max_browsers: int | None = None,
    max_consultas_por_browser: int | None = None,
    incluir_base64: bool = True,
) -> Dict[str, Any]:
    from playwright.async_api import async_playwright

    if not itens:
        return {
            "resultados": [],
            "meta_execucao": {
                "total_consultas": 0,
                "max_browsers": 0,
                "max_consultas_por_browser": 0,
                "capacidade_paralela_total": 0,
                "blocos_fila": 0,
            },
        }

    browsers, por_browser = get_runtime_limits(max_browsers, max_consultas_por_browser)
    blocos = list(_chunked(itens, por_browser))
    sem = asyncio.Semaphore(browsers)

    async with async_playwright() as pw:
        async def _executar_bloco_com_fila(indice_bloco: int, bloco: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            async with sem:
                browser_lote = (indice_bloco % browsers) + 1
                return await _executar_bloco_no_browser(
                    pw,
                    bloco,
                    browser_lote=browser_lote,
                    indice_bloco=indice_bloco,
                    limite_consultas_por_browser=por_browser,
                    headless=headless,
                    incluir_base64=incluir_base64,
                )

        tarefas = [
            asyncio.create_task(_executar_bloco_com_fila(indice_bloco, bloco))
            for indice_bloco, bloco in enumerate(blocos)
        ]
        resultados_por_bloco = await asyncio.gather(*tarefas)

    resultados = [item for bloco in resultados_por_bloco for item in bloco]
    resultados.sort(key=lambda r: int(r.get("indice_entrada", 0)))

    return {
        "resultados": resultados,
        "meta_execucao": {
            "total_consultas": len(itens),
            "max_browsers": browsers,
            "max_consultas_por_browser": por_browser,
            "capacidade_paralela_total": browsers * por_browser,
            "blocos_fila": len(blocos),
            "incluir_base64": incluir_base64,
        },
    }
