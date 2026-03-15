import json
import logging
import os
import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional
from playwright.sync_api import sync_playwright

from .browser import create_browser_context
from .navigation import perform_search
from .extraction import extract_personal_info, extract_benefits
from .validators import classificar_consulta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class TransparencyBot:
    def __init__(self, headless: bool = True, alvo: Optional[str] = None, usar_refine: bool = False):
        self.headless = headless
        self.url_base = "https://portaldatransparencia.gov.br/"
        self.alvo = alvo
        # True para usar busca refinada, False para busca simples (Lupa)
        self.usar_refine = usar_refine

    @staticmethod
    def _agora_consulta() -> str:
        agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
        return agora.strftime("%d/%m/%Y %H:%M")

    def _normalizar_pessoa(self, pessoa: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        src = pessoa or {}
        consulta = src.get("consulta") or self.alvo or "N/A"
        return {
            **src,
            "consulta": consulta,
            "nome": src.get("nome") or "N/A",
            "cpf": src.get("cpf") or "N/A",
            "localidade": src.get("localidade") or "N/A",
            "total_recursos_favorecidos": src.get("total_recursos_favorecidos") or "R$ 0,00",
        }

    def _com_auditoria(self, payload: Dict[str, Any], id_consulta: str, data_hora_consulta: str) -> Dict[str, Any]:
        out = dict(payload)
        out["id_consulta"] = id_consulta
        out["data_hora_consulta"] = data_hora_consulta
        out["pessoa"] = self._normalizar_pessoa(out.get("pessoa"))
        meta = dict(out.get("meta") or {})
        meta["id_consulta"] = id_consulta
        meta["data_hora_consulta"] = data_hora_consulta
        meta["total_valor_recebido"] = meta.get("total_valor_recebido", 0.0)
        meta["total_valor_recebido_formatado"] = meta.get("total_valor_recebido_formatado", "R$ 0,00")
        out["meta"] = meta
        return out

    def run(self) -> Dict[str, Any]:
        id_consulta = str(uuid4())
        data_hora_consulta = self._agora_consulta()

        if not self.alvo:
            return self._com_auditoria(
                {"status": "invalid", "error": "Parâmetro 'alvo' não definido."},
                id_consulta,
                data_hora_consulta,
            )

        valido, tipo, alvo_normalizado, motivo = classificar_consulta(self.alvo)
        if not valido:
            logger.warning(f"Entrada inválida: {self.alvo} -> {motivo}")
            return self._com_auditoria(
                {"status": "invalid", "error": motivo, "consulta": self.alvo},
                id_consulta,
                data_hora_consulta,
            )

        # usa valor normalizado
        self.alvo = alvo_normalizado

        with sync_playwright() as pw:
            browser, context, page = create_browser_context(
                pw,
                headless=self.headless,
                user_agent=os.getenv("PLAYWRIGHT_USER_AGENT", DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT,
                viewport={"width": 1280, "height": 720},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
            )

            try:
                # Navegação e busca
                search_result = perform_search(page, self.url_base, self.alvo, self.usar_refine)
                if search_result.get("zero"):
                    return self._com_auditoria({
                        "status": "error",
                        "error": search_result.get("mensagem"),
                        "pessoa": {"consulta": self.alvo, "nome": "N/A", "cpf": "N/A", "localidade": "N/A"},
                        "beneficios": [],
                        "meta": {
                            "resultados_encontrados": 0,
                            "evidencia_resultados_zero": search_result.get("evidencia_base64"),
                            "mensagem": search_result.get("mensagem"),
                        },
                    }, id_consulta, data_hora_consulta)

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
                    return self._com_auditoria({
                        "pessoa": {
                            **self._normalizar_pessoa(pessoal),
                            "nis": None,
                            "quantidade_beneficios": 0,
                            "total_recursos_favorecidos": benefits_data.get("total_valor_recebido_formatado", "R$ 0,00"),
                        },
                        "beneficios": [],
                        "meta": {
                            "resultados_encontrados": search_result.get("quantidade"),
                            "beneficios_encontrados": benefits_data.get("beneficios_encontrados"),
                            "evidencia_sem_beneficio": benefits_data.get("panorama_base64"),
                            "total_valor_recebido": benefits_data.get("total_valor_recebido", 0.0),
                            "total_valor_recebido_formatado": benefits_data.get("total_valor_recebido_formatado", "R$ 0,00"),
                        },
                    }, id_consulta, data_hora_consulta)

                resultado_final = {
                    "pessoa": {
                        **self._normalizar_pessoa(pessoal),
                        "quantidade_beneficios": benefits_data.get("quantidade_beneficios", 0),
                        "total_recursos_favorecidos": benefits_data.get("total_valor_recebido_formatado", "R$ 0,00"),
                    },
                    "beneficios": benefits_data.get("beneficios_resultado"),
                    "meta": {
                        "resultados_encontrados": search_result.get("quantidade"),
                        "beneficios_encontrados": benefits_data.get("beneficios_encontrados"),
                        "panorama_relacao": benefits_data.get("panorama_base64"),
                        "total_valor_recebido": benefits_data.get("total_valor_recebido", 0.0),
                        "total_valor_recebido_formatado": benefits_data.get("total_valor_recebido_formatado", "R$ 0,00"),
                    },
                }

                logger.info(f"Processamento concluído para {pessoal.get('nome') if pessoal else self.alvo}.")
                return self._com_auditoria(resultado_final, id_consulta, data_hora_consulta)

            except Exception as e:
                logger.error(f"Erro durante a execução do bot: {e}", exc_info=True)
                return self._com_auditoria(
                    {"status": "error", "error": str(e)},
                    id_consulta,
                    data_hora_consulta,
                )

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
