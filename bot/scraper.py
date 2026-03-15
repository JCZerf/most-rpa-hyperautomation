import json
import logging
from typing import Any, Dict, Optional
from playwright.sync_api import sync_playwright

from .browser import create_browser_context
from .navigation import perform_search
from .extraction import extract_personal_info, extract_benefits
from .validators import classificar_consulta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransparencyBot:
    def __init__(self, headless: bool = True, alvo: Optional[str] = None, usar_refine: bool = False):
        self.headless = headless
        self.url_base = "https://portaldatransparencia.gov.br/"
        self.alvo = alvo
        # True para usar busca refinada, False para busca simples (Lupa)
        self.usar_refine = usar_refine

    def run(self) -> Dict[str, Any]:
        if not self.alvo:
            return {"status": "invalid", "error": "Parâmetro 'alvo' não definido."}

        valido, tipo, alvo_normalizado, motivo = classificar_consulta(self.alvo)
        if not valido:
            logger.warning(f"Entrada inválida: {self.alvo} -> {motivo}")
            return {"status": "invalid", "error": motivo, "consulta": self.alvo}

        # usa valor normalizado
        self.alvo = alvo_normalizado

        with sync_playwright() as pw:
            browser, context, page = create_browser_context(
                pw,
                headless=self.headless,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )

            try:
                # Navegação e busca
                search_result = perform_search(page, self.url_base, self.alvo, self.usar_refine)
                if search_result.get("zero"):
                    return {
                        "status": "error",
                        "error": search_result.get("mensagem"),
                        "pessoa": {"consulta": self.alvo},
                        "beneficios": [],
                        "meta": {
                            "resultados_encontrados": 0,
                            "evidencia_resultados_zero": search_result.get("evidencia_base64"),
                            "data_consulta": search_result.get("data_consulta"),
                            "hora_consulta": search_result.get("hora_consulta"),
                            "mensagem": search_result.get("mensagem"),
                        },
                    }

                # Extração de dados cadastrais
                pessoal = extract_personal_info(page)

                # Acordeão e detalhamento (extrair benefícios)
                botao_acordeon = page.get_by_role("button", name="Recebimentos de recursos")
                botao_acordeon.scroll_into_view_if_needed()
                botao_acordeon.dispatch_event("click")

                btn_detalhar = page.locator("a:text('Detalhar')").first
                try:
                    btn_detalhar.wait_for(state="visible", timeout=8000)
                except Exception:
                    logger.warning("Botão detalhar não apareceu, tentando clique forçado no acordeão...")
                    botao_acordeon.click(force=True)
                    btn_detalhar.wait_for(state="visible", timeout=5000)

                benefits_data = extract_benefits(context, page, self.url_base)

                # Se nenhum benefício encontrado, montar retorno similar ao original
                if not benefits_data.get("beneficios_encontrados"):
                    return {
                        "pessoa": {**pessoal, "nis": None, "quantidade_beneficios": 0},
                        "beneficios": [],
                        "meta": {
                            "resultados_encontrados": search_result.get("quantidade"),
                            "beneficios_encontrados": benefits_data.get("beneficios_encontrados"),
                            "evidencia_sem_beneficio": benefits_data.get("panorama_base64"),
                            "data_consulta": benefits_data.get("data_consulta"),
                            "hora_consulta": benefits_data.get("hora_consulta"),
                        },
                    }

                resultado_final = {
                    "pessoa": {**pessoal, "quantidade_beneficios": benefits_data.get("quantidade_beneficios", 0)},
                    "beneficios": benefits_data.get("beneficios_resultado"),
                    "meta": {
                        "resultados_encontrados": search_result.get("quantidade"),
                        "beneficios_encontrados": benefits_data.get("beneficios_encontrados"),
                        "panorama_relacao": benefits_data.get("panorama_base64"),
                        "data_consulta": benefits_data.get("data_consulta"),
                        "hora_consulta": benefits_data.get("hora_consulta"),
                    },
                }

                logger.info(f"Processamento concluído para {pessoal.get('nome') if pessoal else self.alvo}.")
                return resultado_final

            except Exception as e:
                logger.error(f"Erro durante a execução do bot: {e}", exc_info=True)
                return {"status": "error", "error": str(e)}

            finally:
                try:
                    if context:
                        context.close()
                except Exception:
                    logger.debug("Falha ao fechar context", exc_info=True)
                try:
                    if browser:
                        browser.close()
                except Exception:
                    logger.debug("Falha ao fechar browser", exc_info=True)
