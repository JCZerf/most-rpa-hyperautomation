import logging
import datetime
import base64
from zoneinfo import ZoneInfo
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def extract_personal_info(page: Any) -> Dict[str, str]:
    nome = page.locator("div.col-sm-4:has(strong:has-text('Nome')) span").inner_text().strip()
    cpf = page.locator("div.col-sm-3:has(strong:has-text('CPF')) span").inner_text().strip()
    localidade = page.locator("div.col-sm-3:has(strong:has-text('Localidade')) span").inner_text().strip()
    return {"nome": nome, "cpf": cpf, "localidade": localidade}


def extract_benefits(context: Any, page: Any, url_base: str) -> Dict[str, Any]:
    # Captura panorama
    panorama_bytes = page.screenshot(full_page=True)
    panorama_base64 = base64.b64encode(panorama_bytes).decode("utf-8")
    logger.info("Panorama capturado em base64.")

    beneficios_possiveis = ["Auxílio Brasil", "Auxílio Emergencial", "Bolsa Família"]
    beneficios_encontrados: List[str] = []
    for b in beneficios_possiveis:
        if page.locator(f"strong:has-text('{b}')").count() > 0:
            beneficios_encontrados.append(b)

    if not beneficios_encontrados:
        agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
        data_consulta = agora.strftime("%d/%m/%Y")
        hora_consulta = agora.strftime("%H:%M")
        return {
            "beneficios_encontrados": beneficios_encontrados,
            "panorama_base64": panorama_base64,
            "resultado": {
                "beneficios": [],
                "meta": {
                    "beneficios_encontrados": beneficios_encontrados,
                    "evidencia_sem_beneficio": panorama_base64,
                    "data_consulta": data_consulta,
                    "hora_consulta": hora_consulta,
                },
            },
        }

    beneficios_resultado: List[Dict[str, Any]] = []
    blocos = page.locator("#accordion-recebimentos-recursos .br-table")
    for i in range(blocos.count()):
        bloco = blocos.nth(i)
        try:
            tipo = bloco.locator("strong").inner_text().strip()
        except Exception:
            tipo = bloco.inner_text().strip().split('\n', 1)[0][:50]

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

                try:
                    if nova_pagina.locator("table#tabelaDetalheValoresRecebidos").count():
                        tabela = nova_pagina.locator("table#tabelaDetalheValoresRecebidos")
                        tabela.locator("tbody td").first.wait_for(state="visible", timeout=10000)
                        nova_pagina.wait_for_timeout(300)
                        linhas = tabela.locator("tbody tr")
                        for r in range(linhas.count()):
                            cols = linhas.nth(r).locator("td")
                            if cols.count() >= 6:
                                detalhe_parcelas.append({
                                    "mes_folha": cols.nth(0).inner_text().strip(),
                                    "mes_referencia": cols.nth(1).inner_text().strip(),
                                    "uf": cols.nth(2).inner_text().strip(),
                                    "municipio": cols.nth(3).inner_text().strip(),
                                    "quantidade_dependentes": cols.nth(4).inner_text().strip(),
                                    "valor": cols.nth(5).inner_text().strip(),
                                })
                    elif nova_pagina.locator("table#tabelaDetalheDisponibilizado").count():
                        tabela = nova_pagina.locator("table#tabelaDetalheDisponibilizado")
                        tabela.locator("tbody td").first.wait_for(state="visible", timeout=10000)
                        nova_pagina.wait_for_timeout(300)
                        linhas = tabela.locator("tbody tr")
                        for r in range(linhas.count()):
                            cols = linhas.nth(r).locator("td")
                            if cols.count() >= 7:
                                detalhe_parcelas.append({
                                    "mes_disponibilizacao": cols.nth(0).inner_text().strip(),
                                    "parcela": cols.nth(1).inner_text().strip(),
                                    "uf": cols.nth(2).inner_text().strip(),
                                    "municipio": cols.nth(3).inner_text().strip(),
                                    "enquadramento": cols.nth(4).inner_text().strip(),
                                    "valor": cols.nth(5).inner_text().strip(),
                                    "observacao": cols.nth(6).inner_text().strip(),
                                })
                    elif nova_pagina.locator("table#tabelaDetalheValoresSacados").count():
                        tabela = nova_pagina.locator("table#tabelaDetalheValoresSacados")
                        tabela.locator("tbody td").first.wait_for(state="visible", timeout=10000)
                        nova_pagina.wait_for_timeout(300)
                        linhas = tabela.locator("tbody tr")
                        for r in range(linhas.count()):
                            cols = linhas.nth(r).locator("td")
                            if cols.count() >= 5:
                                detalhe_parcelas.append({
                                    "mes_folha": cols.nth(0).inner_text().strip(),
                                    "mes_referencia": cols.nth(1).inner_text().strip(),
                                    "uf": cols.nth(2).inner_text().strip(),
                                    "municipio": cols.nth(3).inner_text().strip(),
                                    "valor_parcela": cols.nth(4).inner_text().strip(),
                                })
                    else:
                        tabela = None
                        if nova_pagina.locator("table#tabelaDetalheDisponibilizado").count():
                            tabela = nova_pagina.locator("table#tabelaDetalheDisponibilizado")
                        else:
                            tables = nova_pagina.locator("table")
                            for ti in range(tables.count()):
                                if tables.nth(ti).locator("tbody tr").count() > 0:
                                    tabela = tables.nth(ti)
                                    break
                        if tabela:
                            tabela.locator("tbody td").first.wait_for(state="visible", timeout=10000)
                            nova_pagina.wait_for_timeout(300)
                            linhas = tabela.locator("tbody tr")
                            for r in range(linhas.count()):
                                cols = linhas.nth(r).locator("td")
                                if cols.count() >= 1:
                                    row = [cols.nth(ci).inner_text().strip() for ci in range(cols.count())]
                                    detalhe_parcelas.append({f"col_{idx}": val for idx, val in enumerate(row)})
                except Exception:
                    detalhe_parcelas = []

                try:
                    bytes_det = nova_pagina.screenshot(full_page=True)
                    detalhe_evidence_b64 = base64.b64encode(bytes_det).decode("utf-8")
                except Exception:
                    detalhe_evidence_b64 = None

                try:
                    nova_pagina.close()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Falha ao abrir detalhe para {tipo}: {e}")

        beneficios_resultado.append({
            "tipo": tipo,
            "nis": nis_benef,
            "valor_recebido": valor_recebido,
            "detalhe_href": href,
            "detalhe_evidencia": detalhe_evidence_b64,
            "parcelas": detalhe_parcelas,
        })

    agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
    data_consulta = agora.strftime("%d/%m/%Y")
    hora_consulta = agora.strftime("%H:%M")

    return {
        "beneficios_resultado": beneficios_resultado,
        "beneficios_encontrados": beneficios_encontrados,
        "panorama_base64": panorama_base64,
        "data_consulta": data_consulta,
        "hora_consulta": hora_consulta,
    }
