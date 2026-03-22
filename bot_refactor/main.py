import argparse
import asyncio
import json
import logging
from typing import Any, Dict, List

from playwright.async_api import async_playwright

from bot_refactor.browser import create_browser_context_async
from bot_refactor.identity import get_random_profile
from bot_refactor.scraper import TransparencyBotAsync

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

IMAGE_PAYLOAD_KEYS = {
    "evidencia_base64",
    "evidencia_resultados_zero",
    "evidencia_sem_beneficio",
    "detalhe_evidencia",
    "panorama_base64",
    "panorama_relacao",
}

DEFAULT_TEST_CONSULTAS = [
    "A DILA DA SILVA BRITO LIMA",
    "BA N TCHI OLIVE CONFORTE N DAH KOUAGOU",
    "CAA SANTOS BARROS MACHADO",
    "D ANGELA ALVES DE BARROS FELIPE",
    "E DILA LARISSA RODRIGUES BERTOLDO",
    "F MAGNIFICAT ZINSOU",
    "G DEON DA SILVA VIEIRA",
    "HA MOHAMMAD OLIUR RAHMAN",
    "I DINA APARECIDA DA SILVA GARCIA",
    "J QUECEMIRA BATISTA DOS SANTOS",
    "K TIANA MARLEN SILVA ARAUJO",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Executa o bot async de forma isolada (refactor).")
    parser.add_argument(
        "--consulta",
        action="append",
        dest="consultas",
        help="CPF/NIS/Nome para consulta. Pode repetir a flag para montar um lote.",
    )
    parser.add_argument(
        "--consultas-json",
        help='Lista JSON de consultas (ex: \'["04031769644","A ANNE CHRISTINE SILVA RIBEIRO"]\').',
    )
    parser.add_argument(
        "--refinar-busca",
        action="store_true",
        help="Ativa fluxo refinado do portal (equivalente a refinar_busca=true).",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Executa com navegador visível (headless=false).",
    )
    parser.add_argument(
        "--limite-consultas-por-browser",
        type=int,
        default=4,
        help="Quantidade máxima de consultas por browser/página antes de rotacionar (padrão: 4).",
    )
    parser.add_argument(
        "--modo-dev-sem-imagens",
        action="store_true",
        help="Remove evidências/imagens Base64 do JSON de saída para facilitar depuração local.",
    )
    return parser.parse_args()


def _normalizar_consultas(args: argparse.Namespace) -> List[str]:
    consultas: List[str] = list(args.consultas or [])

    if args.consultas_json:
        try:
            parsed = json.loads(args.consultas_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--consultas-json inválido: {exc}") from exc
        if not isinstance(parsed, list):
            raise ValueError("--consultas-json deve ser uma lista JSON.")
        consultas.extend("" if item is None else str(item) for item in parsed)

    consultas = [c.strip() for c in consultas if str(c).strip()]
    if not consultas:
        logger.info(
            "Nenhum alvo informado via CLI. Usando lista padrão de testes (%s consultas).",
            len(DEFAULT_TEST_CONSULTAS),
        )
        return list(DEFAULT_TEST_CONSULTAS)
    return consultas


def _chunked(items: List[str], size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _remover_imagens_base64(valor: Any) -> Any:
    if isinstance(valor, dict):
        novo = {}
        for chave, conteudo in valor.items():
            chave_lower = chave.lower()
            if chave in IMAGE_PAYLOAD_KEYS or "evidencia" in chave_lower or "base64" in chave_lower:
                continue
            novo[chave] = _remover_imagens_base64(conteudo)
        return novo
    if isinstance(valor, list):
        return [_remover_imagens_base64(item) for item in valor]
    return valor


async def _executar_consulta_em_aba(
    context: Any,
    consulta: str,
    *,
    indice_browser: int,
    ordem_no_browser: int,
    limite_consultas_por_browser: int,
    headless: bool,
    usar_refine: bool,
) -> Dict[str, Any]:
    page = await context.new_page()

    try:
        logger.info(
            "Browser %s | aba %s/%s iniciada: %s",
            indice_browser,
            ordem_no_browser,
            limite_consultas_por_browser,
            consulta,
        )
        bot = TransparencyBotAsync(headless=headless, alvo=consulta, usar_refine=usar_refine)
        resultado = await bot.run_with_page_async(context, page)

        meta = dict(resultado.get("meta") or {})
        meta["browser_lote"] = indice_browser
        meta["ordem_no_browser"] = ordem_no_browser
        meta["limite_consultas_por_browser"] = limite_consultas_por_browser
        meta["execucao_paralela_mesmo_browser"] = True
        resultado["meta"] = meta

        return {
            "consulta": consulta,
            "browser_lote": indice_browser,
            "ordem_no_browser": ordem_no_browser,
            "resultado": resultado,
        }
    except Exception as exc:
        logger.exception(
            "Falha não tratada na aba %s do browser %s (consulta=%s)",
            ordem_no_browser,
            indice_browser,
            consulta,
        )
        return {
            "consulta": consulta,
            "browser_lote": indice_browser,
            "ordem_no_browser": ordem_no_browser,
            "resultado": {
                "status": "error",
                "error": str(exc),
                "meta": {
                    "browser_lote": indice_browser,
                    "ordem_no_browser": ordem_no_browser,
                    "limite_consultas_por_browser": limite_consultas_por_browser,
                    "execucao_paralela_mesmo_browser": True,
                },
            },
        }
    finally:
        try:
            await page.close()
        except Exception:
            logger.debug(
                "Falha ao fechar aba %s do browser %s",
                ordem_no_browser,
                indice_browser,
                exc_info=True,
            )


async def _executar_bloco_no_browser(
    pw: Any,
    consultas_bloco: List[str],
    *,
    indice_browser: int,
    limite_consultas_por_browser: int,
    headless: bool,
    usar_refine: bool,
) -> List[Dict[str, Any]]:
    perfil = get_random_profile()
    logger.info(
        "Abrindo browser %s para %s consulta(s) (perfil=%s)",
        indice_browser,
        len(consultas_bloco),
        perfil["name"],
    )

    browser, context, page = await create_browser_context_async(
        pw,
        headless=headless,
        user_agent=perfil["user_agent"],
        viewport=perfil["viewport"],
        locale=perfil["locale"],
        timezone_id=perfil["timezone_id"],
    )

    saida_bloco: List[Dict[str, Any]] = []
    try:
        try:
            await page.close()
        except Exception:
            logger.debug("Falha ao fechar aba inicial do browser %s", indice_browser, exc_info=True)

        logger.info(
            "Browser %s executará %s consulta(s) em paralelo por abas.",
            indice_browser,
            len(consultas_bloco),
        )
        tarefas = []
        for ordem_no_browser, consulta in enumerate(consultas_bloco, start=1):
            tarefas.append(
                asyncio.create_task(
                    _executar_consulta_em_aba(
                        context,
                        consulta,
                        indice_browser=indice_browser,
                        ordem_no_browser=ordem_no_browser,
                        limite_consultas_por_browser=limite_consultas_por_browser,
                        headless=headless,
                        usar_refine=usar_refine,
                    )
                )
            )
        saida_bloco = await asyncio.gather(*tarefas)
        return saida_bloco
    finally:
        try:
            await context.close()
        except Exception:
            logger.debug("Falha ao fechar context do browser %s", indice_browser, exc_info=True)
        try:
            await browser.close()
        except Exception:
            logger.debug("Falha ao fechar browser %s", indice_browser, exc_info=True)


async def _run() -> int:
    args = _parse_args()
    consultas = _normalizar_consultas(args)

    limite = int(args.limite_consultas_por_browser)
    if limite <= 0:
        raise ValueError("--limite-consultas-por-browser deve ser maior que zero.")

    headless = not args.headed
    usar_refine = args.refinar_busca
    blocos = list(_chunked(consultas, limite))

    logger.info(
        "Iniciando execução isolada do refactor: total_consultas=%s, limite_por_browser=%s, browsers_previstos=%s, headless=%s, refinar_busca=%s",
        len(consultas),
        limite,
        len(blocos),
        headless,
        usar_refine,
    )

    resultados: List[Dict[str, Any]] = []
    async with async_playwright() as pw:
        tarefas_browsers = []
        for indice_browser, bloco in enumerate(blocos, start=1):
            tarefas_browsers.append(
                asyncio.create_task(
                    _executar_bloco_no_browser(
                        pw,
                        bloco,
                        indice_browser=indice_browser,
                        limite_consultas_por_browser=limite,
                        headless=headless,
                        usar_refine=usar_refine,
                    )
                )
            )

        resultados_por_browser = await asyncio.gather(*tarefas_browsers)
        for resultado_bloco in resultados_por_browser:
            resultados.extend(resultado_bloco)

    tem_erro_execucao = any((item.get("resultado") or {}).get("status") == "error" for item in resultados)

    if len(resultados) == 1:
        payload_saida: Any = resultados[0]["resultado"]
        if args.modo_dev_sem_imagens:
            payload_saida = _remover_imagens_base64(payload_saida)
        print(json.dumps(payload_saida, ensure_ascii=False, indent=2))
    else:
        payload = {
            "resultados": resultados,
            "meta_execucao": {
                "total_consultas": len(consultas),
                "limite_consultas_por_browser": limite,
                "browsers_utilizados": len(blocos),
                "modo_dev_sem_imagens": args.modo_dev_sem_imagens,
            },
        }
        payload_saida = _remover_imagens_base64(payload) if args.modo_dev_sem_imagens else payload
        print(json.dumps(payload_saida, ensure_ascii=False, indent=2))

    return 1 if tem_erro_execucao else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))
