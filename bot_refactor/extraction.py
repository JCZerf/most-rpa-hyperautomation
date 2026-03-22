import base64
import datetime
import logging
import unicodedata
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from .logging_utils import log_event
from .utils import formatar_brl, valor_texto_para_float

logger = logging.getLogger(__name__)


async def extract_personal_info_async(page: Any) -> Dict[str, str]:
    nome = (await page.locator("div.col-sm-4:has(strong:has-text('Nome')) span").inner_text()).strip()
    cpf = (await page.locator("div.col-sm-3:has(strong:has-text('CPF')) span").inner_text()).strip()
    localidade = (await page.locator("div.col-sm-3:has(strong:has-text('Localidade')) span").inner_text()).strip()
    return {"nome": nome, "cpf": cpf, "localidade": localidade}


def _agora_brt() -> Dict[str, str]:
    agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
    return {"data_consulta": agora.strftime("%d/%m/%Y"), "hora_consulta": agora.strftime("%H:%M")}


async def _detectar_beneficios_painel(page: Any) -> List[str]:
    beneficios_possiveis = ["Auxílio Brasil", "Auxílio Emergencial", "Bolsa Família"]
    encontrados: List[str] = []
    for beneficio in beneficios_possiveis:
        if await page.locator(f"strong:has-text('{beneficio}')").count() > 0:
            encontrados.append(beneficio)
    return encontrados


async def _extrair_textos_cols(cols: Any) -> List[str]:
    total = await cols.count()
    return [(await cols.nth(ci).inner_text()).strip() for ci in range(total)]


def _parse_linha_valores_recebidos(valores: List[str]) -> Dict[str, str] | None:
    if len(valores) < 6:
        return None
    return {
        "mes_folha": valores[0],
        "mes_referencia": valores[1],
        "uf": valores[2],
        "municipio": valores[3],
        "quantidade_dependentes": valores[4],
        "valor": valores[5],
    }


def _parse_linha_disponibilizado(valores: List[str]) -> Dict[str, str] | None:
    if len(valores) < 7:
        return None
    return {
        "mes_disponibilizacao": valores[0],
        "parcela": valores[1],
        "uf": valores[2],
        "municipio": valores[3],
        "enquadramento": valores[4],
        "valor": valores[5],
        "observacao": valores[6],
    }


def _parse_linha_valores_sacados(valores: List[str]) -> Dict[str, str] | None:
    if len(valores) < 5:
        return None
    return {
        "mes_folha": valores[0],
        "mes_referencia": valores[1],
        "uf": valores[2],
        "municipio": valores[3],
        "valor_parcela": valores[4],
    }


def _parse_linha_generica(valores: List[str]) -> Dict[str, str] | None:
    if not valores:
        return None
    return {f"col_{idx}": val for idx, val in enumerate(valores)}


async def _coletar_linhas_tabela(tabela: Any, nova_pagina: Any, parser) -> List[Dict[str, str]]:
    detalhes: List[Dict[str, str]] = []
    await tabela.locator("tbody td").first.wait_for(state="visible", timeout=10000)
    await nova_pagina.wait_for_timeout(300)
    linhas = tabela.locator("tbody tr")
    total_linhas = await linhas.count()
    for r in range(total_linhas):
        cols = linhas.nth(r).locator("td")
        valores = await _extrair_textos_cols(cols)
        parsed = parser(valores)
        if parsed:
            detalhes.append(parsed)
    return detalhes


async def _encontrar_tabela_fallback(nova_pagina: Any) -> Any | None:
    if await nova_pagina.locator("table#tabelaDetalheDisponibilizado").count():
        return nova_pagina.locator("table#tabelaDetalheDisponibilizado")

    tables = nova_pagina.locator("table")
    total = await tables.count()
    for ti in range(total):
        tabela = tables.nth(ti)
        if await tabela.locator("tbody tr").count() > 0:
            return tabela
    return None


async def _coletar_detalhe_parcelas(nova_pagina: Any) -> List[Dict[str, str]]:
    try:
        if await nova_pagina.locator("table#tabelaDetalheValoresRecebidos").count():
            tabela = nova_pagina.locator("table#tabelaDetalheValoresRecebidos")
            return await _coletar_linhas_tabela(tabela, nova_pagina, _parse_linha_valores_recebidos)

        if await nova_pagina.locator("table#tabelaDetalheDisponibilizado").count():
            tabela = nova_pagina.locator("table#tabelaDetalheDisponibilizado")
            return await _coletar_linhas_tabela(tabela, nova_pagina, _parse_linha_disponibilizado)

        if await nova_pagina.locator("table#tabelaDetalheValoresSacados").count():
            tabela = nova_pagina.locator("table#tabelaDetalheValoresSacados")
            return await _coletar_linhas_tabela(tabela, nova_pagina, _parse_linha_valores_sacados)

        tabela = await _encontrar_tabela_fallback(nova_pagina)
        if tabela:
            return await _coletar_linhas_tabela(tabela, nova_pagina, _parse_linha_generica)
    except Exception:
        return []
    return []


async def _detectar_verificacao_humana(nova_pagina: Any) -> bool:
    def _normalizar(texto: str) -> str:
        base = unicodedata.normalize("NFD", texto or "")
        base = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
        return base.lower()

    try:
        titulo = _normalizar(await nova_pagina.title() or "")
    except Exception:
        titulo = ""

    try:
        corpo = _normalizar(await nova_pagina.inner_text("body", timeout=2000) or "")
    except Exception:
        corpo = ""

    sinais = [
        "human verification",
        "vamos confirmar que voce e humano",
        "conclua a verificacao de seguranca antes de continuar",
        "essa etapa verifica se voce nao e um bot",
        "evitar spam",
        "iniciar",
    ]
    texto = f"{titulo}\n{corpo}"
    return any(s in texto for s in sinais)


async def extract_benefits_async(context: Any, page: Any, url_base: str) -> Dict[str, Any]:
    panorama_bytes = await page.screenshot(full_page=True)
    panorama_base64 = base64.b64encode(panorama_bytes).decode("utf-8")
    log_event(logger, logging.INFO, "panorama_capturado")

    beneficios_encontrados = await _detectar_beneficios_painel(page)
    log_event(logger, logging.INFO, "beneficios_detectados_painel", beneficios=beneficios_encontrados)

    if not beneficios_encontrados:
        ts = _agora_brt()
        return {
            "beneficios_encontrados": beneficios_encontrados,
            "panorama_base64": panorama_base64,
            "total_valor_recebido": 0.0,
            "total_valor_recebido_formatado": formatar_brl(0.0),
            "resultado": {
                "beneficios": [],
                "meta": {
                    "beneficios_encontrados": beneficios_encontrados,
                    "evidencia_sem_beneficio": panorama_base64,
                    "data_consulta": ts["data_consulta"],
                    "hora_consulta": ts["hora_consulta"],
                },
            },
        }

    beneficios_resultado: List[Dict[str, Any]] = []
    blocos = page.locator("#accordion-recebimentos-recursos .br-table")
    total_blocos = await blocos.count()
    log_event(logger, logging.INFO, "inicio_extracao_beneficios", total_blocos=total_blocos)

    for i in range(total_blocos):
        bloco = blocos.nth(i)
        try:
            tipo = (await bloco.locator("strong").inner_text()).strip()
        except Exception:
            tipo = (await bloco.inner_text()).strip().split("\n", 1)[0][:50]

        log_event(logger, logging.INFO, "extraindo_beneficio", indice=i + 1, total=total_blocos, tipo=tipo)

        try:
            cols = bloco.locator("table tbody tr td")
            cols_count = await cols.count()
            nis_texto = (await cols.nth(1).inner_text()).strip() if cols_count > 1 else ""
            nis_benef = " ".join(nis_texto.split())
            valor_recebido = (await cols.last.inner_text()).strip() if cols_count >= 4 else ""
        except Exception:
            nis_benef = None
            valor_recebido = ""

        try:
            href = await bloco.locator("tbody tr a").first.get_attribute("href")
        except Exception:
            href = None

        detalhe_parcelas: List[Dict[str, str]] = []
        detalhe_evidence_b64 = None
        detalhe_status = "ok"
        detalhe_mensagem = None

        if href:
            try:
                detalhe_url = href if href.startswith("http") else url_base.rstrip("/") + href
                nova_pagina = await context.new_page()
                await nova_pagina.goto(detalhe_url, wait_until="networkidle")
                try:
                    await nova_pagina.wait_for_selector(".loading-grande", timeout=2000)
                    await nova_pagina.wait_for_selector(".loading-grande", state="hidden", timeout=20000)
                except Exception:
                    pass

                if await _detectar_verificacao_humana(nova_pagina):
                    detalhe_status = "human_verification"
                    detalhe_mensagem = (
                        "Vamos confirmar que você é humano. Conclua a verificação de segurança antes de continuar."
                    )
                    log_event(
                        logger,
                        logging.WARNING,
                        "verificacao_humana_detectada_detalhe",
                        tipo=tipo,
                        detalhe_url=detalhe_url,
                    )
                else:
                    detalhe_parcelas = await _coletar_detalhe_parcelas(nova_pagina)

                if detalhe_status == "ok":
                    try:
                        bytes_det = await nova_pagina.screenshot(full_page=True)
                        detalhe_evidence_b64 = base64.b64encode(bytes_det).decode("utf-8")
                    except Exception:
                        detalhe_evidence_b64 = None

                log_event(logger, logging.INFO, "detalhe_beneficio_finalizado", tipo=tipo, parcelas=len(detalhe_parcelas))

                try:
                    await nova_pagina.close()
                except Exception:
                    pass
            except Exception as e:
                log_event(logger, logging.WARNING, "falha_abrir_detalhe_beneficio", tipo=tipo, erro=str(e))

        beneficios_resultado.append(
            {
                "beneficio_ordem": f"beneficio_{i + 1}",
                "indice_beneficio": i,
                "tipo": tipo,
                "nis": nis_benef,
                "valor_recebido": valor_recebido,
                "detalhe_href": href,
                "detalhe_evidencia": detalhe_evidence_b64,
                "detalhe_status": detalhe_status,
                "detalhe_mensagem": detalhe_mensagem,
                "parcelas": detalhe_parcelas,
            }
        )

    ts = _agora_brt()

    quantidade_beneficios = len(beneficios_resultado)
    total_valor_recebido = sum(valor_texto_para_float(b.get("valor_recebido", "")) for b in beneficios_resultado)

    return {
        "beneficios_resultado": beneficios_resultado,
        "beneficios_encontrados": beneficios_encontrados,
        "quantidade_beneficios": quantidade_beneficios,
        "total_valor_recebido": total_valor_recebido,
        "total_valor_recebido_formatado": formatar_brl(total_valor_recebido),
        "panorama_base64": panorama_base64,
        "data_consulta": ts["data_consulta"],
        "hora_consulta": ts["hora_consulta"],
    }
