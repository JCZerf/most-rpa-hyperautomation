import logging
import datetime
import base64
import json
import re
import unicodedata
from zoneinfo import ZoneInfo
from typing import Any, Dict

logger = logging.getLogger(__name__)

LIMIAR_MUITOS_RESULTADOS = 5


def _agora_consulta() -> Dict[str, str]:
    agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
    data_consulta = agora.strftime("%d/%m/%Y")
    hora_consulta = agora.strftime("%H:%M")
    data_hora_consulta = f"{data_consulta} {hora_consulta}"
    return {
        "data_consulta": data_consulta,
        "hora_consulta": hora_consulta,
        "data_hora_consulta": data_hora_consulta,
    }


def _extrair_next_interval(texto: str) -> int | None:
    if not texto:
        return None
    match = re.search(r'"next_interval"\s*:\s*(\d+)', texto)
    if match:
        return int(match.group(1))
    return None


def _detectar_bloqueio_waf(page: Any) -> Dict[str, Any]:
    sinais = []
    proximo_intervalo = None

    url_atual = (getattr(page, "url", "") or "").lower()
    if "awswaf" in url_atual or "edge.sdk.awswaf.com" in url_atual:
        sinais.append("url_waf")

    html = ""
    try:
        html = page.content() or ""
    except Exception:
        html = ""

    html_lower = html.lower()
    if "awswaf" in html_lower or "edge.sdk.awswaf.com" in html_lower:
        sinais.append("html_waf")

    corpo = ""
    try:
        corpo = page.locator("body").inner_text(timeout=1500) or ""
    except Exception:
        corpo = ""

    texto = corpo if corpo else html
    if "next_interval" in texto:
        sinais.append("telemetry_next_interval")
        proximo_intervalo = _extrair_next_interval(texto)

    try:
        storage = page.evaluate(
            """() => {
                try {
                    const out = {};
                    const ls = window.localStorage || {};
                    for (let i = 0; i < ls.length; i++) {
                        const k = ls.key(i);
                        if (k && k.toLowerCase().includes('waf')) {
                            out[k] = ls.getItem(k);
                        }
                    }
                    return out;
                } catch (_) {
                    return {};
                }
            }"""
        )
    except Exception:
        storage = {}

    if isinstance(storage, dict) and storage:
        sinais.append("local_storage_waf")
        if proximo_intervalo is None:
            for valor in storage.values():
                if isinstance(valor, str):
                    proximo_intervalo = _extrair_next_interval(valor)
                    if proximo_intervalo is not None:
                        break

    return {
        "blocked": bool(sinais),
        "next_interval_ms": proximo_intervalo,
        "detected_by": sinais,
    }


def _normalizar_nome(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFD", texto or "")
    sem_acentos = "".join(ch for ch in sem_acentos if unicodedata.category(ch) != "Mn")
    sem_acentos = sem_acentos.upper()
    sem_acentos = re.sub(r"[^A-Z0-9\s]", " ", sem_acentos)
    sem_acentos = re.sub(r"\s+", " ", sem_acentos).strip()
    return sem_acentos


def _nome_corresponde_busca(alvo: str, primeiro_resultado: str) -> bool:
    alvo_n = _normalizar_nome(alvo)
    res_n = _normalizar_nome(primeiro_resultado)

    if not alvo_n or not res_n:
        return False

    if alvo_n == res_n or alvo_n in res_n or res_n in alvo_n:
        return True

    stopwords = {"A", "O", "AS", "OS", "DE", "DA", "DO", "DAS", "DOS", "E"}
    tokens = [t for t in alvo_n.split() if t not in stopwords and len(t) > 2]
    if not tokens:
        tokens = alvo_n.split()

    if not tokens:
        return False

    acertos = sum(1 for t in tokens if t in res_n)
    min_acertos = max(2, int(len(tokens) * 0.6))
    return acertos >= min_acertos


def perform_search(page: Any, url_base: str, alvo: str, usar_refine: bool) -> Dict[str, Any]:
    logger.info(f"Iniciando busca para: {alvo}")
    page.goto(url_base, wait_until="networkidle")

    bloqueio = _detectar_bloqueio_waf(page)
    if bloqueio.get("blocked"):
        tempo = _agora_consulta()
        evidencia_bytes = page.screenshot(full_page=True)
        evidencia_base64 = base64.b64encode(evidencia_bytes).decode("utf-8")
        mensagem = "Bloqueio temporário detectado pelo WAF do portal"
        return {
            "blocked": True,
            "evidencia_base64": evidencia_base64,
            **tempo,
            "quantidade": 0,
            "mensagem": mensagem,
            "next_interval_ms": bloqueio.get("next_interval_ms"),
            "detected_by": bloqueio.get("detected_by"),
        }

    try:
        page.get_by_role("button", name="acceptButtonLabel").click()
    except Exception:
        pass

    page.locator("div:nth-child(10) > .flipcard > .flipcard-wrap > .card.card-back > .card-body").click(force=True)
    page.locator("#button-consulta-pessoa-fisica").click()

    input_busca = page.get_by_role("searchbox", name="Busque por Nome, Nis ou CPF (")
    input_busca.click()
    input_busca.fill(alvo)

    if usar_refine:
        logger.info("Fluxo: Busca Refinada selecionado.")
        refine_button = page.get_by_role("button", name="Refine a Busca")
        try:
            refine_button.click(timeout=5000)
        except Exception:
            refine_button.click(force=True, timeout=5000)

        # O label pode aparecer com variação de texto ou estar fora da área visível.
        # Marcamos direto o checkbox com fallback forçado/JS para evitar timeout intermitente.
        filtro_beneficiario = page.locator("#beneficiarioProgramaSocial")
        try:
            filtro_beneficiario.check(timeout=5000)
        except Exception:
            try:
                filtro_beneficiario.check(force=True, timeout=5000)
            except Exception:
                page.eval_on_selector(
                    "#beneficiarioProgramaSocial",
                    """(el) => {
                        el.checked = true;
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }""",
                )

        page.locator("#btnConsultarPF").click()
    else:
        logger.info("Fluxo: Busca Simples (Lupa) selecionado.")
        page.locator('button[aria-label^="Enviar dados do formulário de busca"]').click()

    page.wait_for_load_state("networkidle")
    contador_locator = page.locator("#countResultados")
    try:
        contador_locator.wait_for(state="visible", timeout=15000)
        page.wait_for_function("document.querySelector('#countResultados').innerText.trim() !== ''")
    except Exception:
        bloqueio = _detectar_bloqueio_waf(page)
        if bloqueio.get("blocked"):
            tempo = _agora_consulta()
            evidencia_bytes = page.screenshot(full_page=True)
            evidencia_base64 = base64.b64encode(evidencia_bytes).decode("utf-8")
            mensagem = "Bloqueio temporário detectado pelo WAF do portal"
            return {
                "blocked": True,
                "evidencia_base64": evidencia_base64,
                **tempo,
                "quantidade": 0,
                "mensagem": mensagem,
                "next_interval_ms": bloqueio.get("next_interval_ms"),
                "detected_by": bloqueio.get("detected_by"),
            }
        raise

    quantidade_texto = contador_locator.inner_text().strip()
    quantidade = int(quantidade_texto.replace('.', '')) if quantidade_texto else 0
    logger.info(f"Resultados encontrados: {quantidade}")

    if quantidade > 0:
        primeiro_resultado_nome = page.locator(".link-busca-nome").first.inner_text().strip().upper()
        if any(ch.isdigit() for ch in alvo):
            logger.info("Termo contém dígitos; pulando verificação por nome (busca por NIS/CPF).")
        elif quantidade >= LIMIAR_MUITOS_RESULTADOS:
            logger.info(
                "Busca retornou muitos resultados (%s). Mantendo fluxo e selecionando o primeiro resultado.",
                quantidade,
            )
        else:
            if not _nome_corresponde_busca(alvo, primeiro_resultado_nome):
                logger.warning(
                    "Resultado não corresponde ao alvo (%s vs %s). Tratando como não encontrado.",
                    alvo,
                    primeiro_resultado_nome,
                )
                quantidade = 0

    if quantidade == 0:
        bloqueio = _detectar_bloqueio_waf(page)
        if bloqueio.get("blocked"):
            tempo = _agora_consulta()
            evidencia_bytes = page.screenshot(full_page=True)
            evidencia_base64 = base64.b64encode(evidencia_bytes).decode("utf-8")
            mensagem = "Bloqueio temporário detectado pelo WAF do portal"
            return {
                "blocked": True,
                "evidencia_base64": evidencia_base64,
                **tempo,
                "quantidade": 0,
                "mensagem": mensagem,
                "next_interval_ms": bloqueio.get("next_interval_ms"),
                "detected_by": bloqueio.get("detected_by"),
            }

        tempo = _agora_consulta()
        evidencia_bytes = page.screenshot(full_page=True)
        evidencia_base64 = base64.b64encode(evidencia_bytes).decode("utf-8")

        if any(ch.isdigit() for ch in alvo):
            mensagem = "Não foi possível retornar os dados no tempo de resposta solicitado"
        else:
            mensagem = f"Foram encontrados 0 resultados para o termo {alvo}"

        return {
            "zero": True,
            "evidencia_base64": evidencia_base64,
            **tempo,
            "quantidade": 0,
            "mensagem": mensagem,
        }

    # Seleciona o primeiro resultado quando houver
    page.locator(".link-busca-nome").first.click()
    return {"zero": False, "quantidade": quantidade}
