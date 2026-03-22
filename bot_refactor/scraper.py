import datetime
import logging
import re
from typing import Any, Dict, Optional
from uuid import uuid4
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

from bot_refactor.identity import get_random_profile

from .browser import create_browser_context_async
from .extraction import extract_benefits_async, extract_personal_info_async
from .logging_utils import bind_id_consulta, log_event, reset_id_consulta
from .navigation import perform_search_async
from .validators import classificar_consulta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransparencyBotAsync:
    def __init__(self, headless: bool = True, alvo: Optional[str] = None, usar_refine: bool = False):
        self.headless = headless
        self.url_base = "https://portaldatransparencia.gov.br/"
        self.alvo = alvo
        self.usar_refine = usar_refine

    @staticmethod
    def _agora_consulta() -> str:
        agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
        return agora.strftime("%d/%m/%Y - %H:%M")

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

    def _validar_entrada(self) -> tuple[bool, Optional[Dict[str, Any]]]:
        if not self.alvo:
            log_event(logger, logging.WARNING, "entrada_invalida", motivo="alvo_ausente")
            return False, {"status": "invalid", "error": "Parâmetro 'alvo' não definido."}

        valido, _tipo, alvo_normalizado, motivo = classificar_consulta(self.alvo)
        if not valido:
            log_event(logger, logging.WARNING, "entrada_invalida", motivo=motivo)
            return False, {"status": "invalid", "error": motivo, "consulta": self.alvo}

        self.alvo = alvo_normalizado
        return True, None

    async def _preparar_detalhes_beneficio(self, page: Any) -> None:
        botao_acordeon = page.get_by_role("button", name="Recebimentos de recursos")
        await botao_acordeon.scroll_into_view_if_needed()
        await botao_acordeon.dispatch_event("click")

        btn_detalhar = page.locator("a:text('Detalhar')").first
        try:
            await btn_detalhar.wait_for(state="visible", timeout=8000)
        except Exception:
            logger.warning("Botão detalhar não apareceu, tentando clique forçado no acordeão...")
            await botao_acordeon.click(force=True)
            await btn_detalhar.wait_for(state="visible", timeout=5000)

    def _resposta_sem_resultado(self, search_result: Dict[str, Any]) -> Dict[str, Any]:
        log_event(logger, logging.INFO, "consulta_sem_resultado", alvo=self.alvo)
        return {
            "status": "not_found",
            "pessoa": {"consulta": self.alvo, "nome": "N/A", "cpf": "N/A", "localidade": "N/A"},
            "beneficios": [],
            "meta": {
                "resultados_encontrados": 0,
                "evidencia_resultados_zero": search_result.get("evidencia_base64"),
                "mensagem": search_result.get("mensagem"),
            },
        }

    def _resposta_sem_beneficios(
        self,
        search_result: Dict[str, Any],
        pessoal: Dict[str, Any],
        benefits_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
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
        }

    def _resposta_final(
        self,
        search_result: Dict[str, Any],
        pessoal: Dict[str, Any],
        benefits_data: Dict[str, Any],
    ) -> Dict[str, Any]:
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
        log_event(
            logger,
            logging.INFO,
            "consulta_concluida",
            alvo=self.alvo,
            nome=pessoal.get("nome") if pessoal else self.alvo,
            resultados=search_result.get("quantidade", 0),
        )
        return resultado_final

    async def _executar_fluxo(self, context: Any, page: Any) -> Dict[str, Any]:
        search_result = await perform_search_async(page, self.url_base, self.alvo, self.usar_refine)
        if search_result.get("zero"):
            return self._resposta_sem_resultado(search_result)

        pessoal = await extract_personal_info_async(page)
        await self._preparar_detalhes_beneficio(page)
        benefits_data = await extract_benefits_async(context, page, self.url_base)

        if not benefits_data.get("beneficios_encontrados"):
            return self._resposta_sem_beneficios(search_result, pessoal, benefits_data)

        return self._resposta_final(search_result, pessoal, benefits_data)

    def _resposta_erro_execucao(self, erro: Exception, id_consulta: str, data_hora_consulta: str) -> Dict[str, Any]:
        log_event(logger, logging.ERROR, "erro_execucao_bot", erro=str(erro))
        logger.error("Erro durante a execução do bot: %s", erro, exc_info=True)
        etapa_falha = None
        match_etapa = re.search(r"\[ETAPA:([^\]]+)\]", str(erro))
        if match_etapa:
            etapa_falha = match_etapa.group(1)

        meta_erro = {}
        if etapa_falha:
            meta_erro["etapa_falha"] = etapa_falha

        return self._com_auditoria(
            {"status": "error", "error": str(erro), "meta": meta_erro},
            id_consulta,
            data_hora_consulta,
        )

    async def run_with_page_async(self, context: Any, page: Any) -> Dict[str, Any]:
        id_consulta = str(uuid4())
        data_hora_consulta = self._agora_consulta()
        token_id = bind_id_consulta(id_consulta)

        try:
            ok, erro_validacao = self._validar_entrada()
            if not ok:
                return self._com_auditoria(erro_validacao, id_consulta, data_hora_consulta)

            try:
                payload = await self._executar_fluxo(context, page)
                return self._com_auditoria(payload, id_consulta, data_hora_consulta)
            except Exception as erro:
                return self._resposta_erro_execucao(erro, id_consulta, data_hora_consulta)
        finally:
            reset_id_consulta(token_id)

    async def run_async(self) -> Dict[str, Any]:
        async with async_playwright() as pw:
            perfil_escolhido = get_random_profile()
            log_event(logger, logging.INFO, "perfil_carregado", nome_perfil=perfil_escolhido["name"])
            browser, context, page = await create_browser_context_async(
                pw,
                headless=self.headless,
                user_agent=perfil_escolhido["user_agent"],
                viewport=perfil_escolhido["viewport"],
                locale=perfil_escolhido["locale"],
                timezone_id=perfil_escolhido["timezone_id"],
            )

            try:
                return await self.run_with_page_async(context, page)
            finally:
                try:
                    if context:
                        await context.close()
                except Exception:
                    logger.debug("Falha ao fechar context", exc_info=True)
                try:
                    if browser:
                        await browser.close()
                except Exception:
                    logger.debug("Falha ao fechar browser", exc_info=True)
