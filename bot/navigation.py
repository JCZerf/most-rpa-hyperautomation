import logging
import datetime
import base64
from zoneinfo import ZoneInfo
from typing import Any, Dict

logger = logging.getLogger(__name__)


def perform_search(page: Any, url_base: str, alvo: str, usar_refine: bool) -> Dict[str, Any]:
    logger.info(f"Iniciando busca para: {alvo}")
    page.goto(url_base, wait_until="networkidle")

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
    contador_locator.wait_for(state="visible", timeout=15000)

    page.wait_for_function("document.querySelector('#countResultados').innerText.trim() !== ''")
    quantidade_texto = contador_locator.inner_text().strip()
    quantidade = int(quantidade_texto.replace('.', '')) if quantidade_texto else 0
    logger.info(f"Resultados encontrados: {quantidade}")

    if quantidade > 0:
        primeiro_resultado_nome = page.locator(".link-busca-nome").first.inner_text().strip().upper()
        if any(ch.isdigit() for ch in alvo):
            logger.info("Termo contém dígitos; pulando verificação por nome (busca por NIS/CPF).")
        else:
            if alvo.upper() not in primeiro_resultado_nome:
                logger.warning(f"Resultados genéricos detectados ({primeiro_resultado_nome}). Tratando como não encontrado.")
                quantidade = 0

    if quantidade == 0:
        agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
        data_consulta = agora.strftime("%d/%m/%Y")
        hora_consulta = agora.strftime("%H:%M")
        evidencia_bytes = page.screenshot(full_page=True)
        evidencia_base64 = base64.b64encode(evidencia_bytes).decode("utf-8")

        if any(ch.isdigit() for ch in alvo):
            mensagem = "Não foi possível retornar os dados no tempo de resposta solicitado"
        else:
            mensagem = f"Foram encontrados 0 resultados para o termo {alvo}"

        return {
            "zero": True,
            "evidencia_base64": evidencia_base64,
            "data_consulta": data_consulta,
            "hora_consulta": hora_consulta,
            "quantidade": 0,
            "mensagem": mensagem,
        }

    # Seleciona o primeiro resultado quando houver
    page.locator(".link-busca-nome").first.click()
    return {"zero": False, "quantidade": quantidade}
