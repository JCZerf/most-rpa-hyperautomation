import logging
import datetime
import base64
from zoneinfo import ZoneInfo
from typing import Any, Dict, List
from .logging_utils import log_event
from .utils import valor_texto_para_float, formatar_brl

logger = logging.getLogger(__name__)


def extract_personal_info(page: Any) -> Dict[str, str]:
    nome = page.locator("div.col-sm-4:has(strong:has-text('Nome')) span").inner_text().strip()
    cpf = page.locator("div.col-sm-3:has(strong:has-text('CPF')) span").inner_text().strip()
    localidade = page.locator("div.col-sm-3:has(strong:has-text('Localidade')) span").inner_text().strip()
    return {"nome": nome, "cpf": cpf, "localidade": localidade}


def _agora_brt() -> Dict[str, str]:
    agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
    return {"data_consulta": agora.strftime("%d/%m/%Y"), "hora_consulta": agora.strftime("%H:%M")}


def _detectar_beneficios_painel(page: Any) -> List[str]:
    beneficios_possiveis = ["Auxílio Brasil", "Auxílio Emergencial", "Bolsa Família"]
    encontrados: List[str] = []
    for beneficio in beneficios_possiveis:
        if page.locator(f"strong:has-text('{beneficio}')").count() > 0:
            encontrados.append(beneficio)
    return encontrados


def _extrair_textos_cols(cols: Any) -> List[str]:
    return [cols.nth(ci).inner_text().strip() for ci in range(cols.count())]


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


def _coletar_linhas_tabela(tabela: Any, nova_pagina: Any, parser) -> List[Dict[str, str]]:
    detalhes: List[Dict[str, str]] = []
    tabela.locator("tbody td").first.wait_for(state="visible", timeout=10000)
    nova_pagina.wait_for_timeout(300)
    linhas = tabela.locator("tbody tr")
    for r in range(linhas.count()):
        cols = linhas.nth(r).locator("td")
        valores = _extrair_textos_cols(cols)
        parsed = parser(valores)
        if parsed:
            detalhes.append(parsed)
    return detalhes


def _encontrar_tabela_fallback(nova_pagina: Any) -> Any | None:
    if nova_pagina.locator("table#tabelaDetalheDisponibilizado").count():
        return nova_pagina.locator("table#tabelaDetalheDisponibilizado")

    tables = nova_pagina.locator("table")
    for ti in range(tables.count()):
        tabela = tables.nth(ti)
        if tabela.locator("tbody tr").count() > 0:
            return tabela
    return None


def _coletar_detalhe_parcelas(nova_pagina: Any) -> List[Dict[str, str]]:
    try:
        if nova_pagina.locator("table#tabelaDetalheValoresRecebidos").count():
            tabela = nova_pagina.locator("table#tabelaDetalheValoresRecebidos")
            return _coletar_linhas_tabela(tabela, nova_pagina, _parse_linha_valores_recebidos)

        if nova_pagina.locator("table#tabelaDetalheDisponibilizado").count():
            tabela = nova_pagina.locator("table#tabelaDetalheDisponibilizado")
            return _coletar_linhas_tabela(tabela, nova_pagina, _parse_linha_disponibilizado)

        if nova_pagina.locator("table#tabelaDetalheValoresSacados").count():
            tabela = nova_pagina.locator("table#tabelaDetalheValoresSacados")
            return _coletar_linhas_tabela(tabela, nova_pagina, _parse_linha_valores_sacados)

        tabela = _encontrar_tabela_fallback(nova_pagina)
        if tabela:
            return _coletar_linhas_tabela(tabela, nova_pagina, _parse_linha_generica)
    except Exception:
        return []
    return []


def extract_benefits(context: Any, page: Any, url_base: str) -> Dict[str, Any]:
    # Captura panorama
    panorama_bytes = page.screenshot(full_page=True)
    panorama_base64 = base64.b64encode(panorama_bytes).decode("utf-8")
    log_event(logger, logging.INFO, "panorama_capturado")

    beneficios_encontrados = _detectar_beneficios_painel(page)

    # log resumo inicial de benefícios detectados
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
    total_blocos = blocos.count()
    log_event(logger, logging.INFO, "inicio_extracao_beneficios", total_blocos=total_blocos)
    for i in range(total_blocos):
        bloco = blocos.nth(i)
        try:
            tipo = bloco.locator("strong").inner_text().strip()
        except Exception:
            tipo = bloco.inner_text().strip().split('\n', 1)[0][:50]

        log_event(logger, logging.INFO, "extraindo_beneficio", indice=i + 1, total=total_blocos, tipo=tipo)

        try:
            cols = bloco.locator("table tbody tr td")
            nis_texto = cols.nth(1).inner_text().strip() if cols.count() > 1 else ""
            nis_benef = " ".join(nis_texto.split())
            valor_recebido = cols.last.inner_text().strip() if cols.count() >= 4 else ""
        except Exception:
            nis_benef = None
            valor_recebido = ""

        try:
            href = bloco.locator("tbody tr a").first.get_attribute("href")
        except Exception:
            href = None

        detalhe_parcelas: List[Dict[str, str]] = []
        detalhe_evidence_b64 = None

        if href:
            try:
                detalhe_url = href if href.startswith("http") else url_base.rstrip("/") + href
                nova_pagina = context.new_page()
                nova_pagina.goto(detalhe_url, wait_until="networkidle")
                try:
                    nova_pagina.wait_for_selector(".loading-grande", timeout=2000)
                    nova_pagina.wait_for_selector(".loading-grande", state="hidden", timeout=20000)
                except Exception:
                    pass

                detalhe_parcelas = _coletar_detalhe_parcelas(nova_pagina)

                try:
                    bytes_det = nova_pagina.screenshot(full_page=True)
                    detalhe_evidence_b64 = base64.b64encode(bytes_det).decode("utf-8")
                except Exception:
                    detalhe_evidence_b64 = None

                log_event(logger, logging.INFO, "detalhe_beneficio_finalizado", tipo=tipo, parcelas=len(detalhe_parcelas))

                try:
                    nova_pagina.close()
                except Exception:
                    pass
            except Exception as e:
                log_event(logger, logging.WARNING, "falha_abrir_detalhe_beneficio", tipo=tipo, erro=str(e))

        beneficios_resultado.append({
            "tipo": tipo,
            "nis": nis_benef,
            "valor_recebido": valor_recebido,
            "detalhe_href": href,
            "detalhe_evidencia": detalhe_evidence_b64,
            "parcelas": detalhe_parcelas,
        })

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
