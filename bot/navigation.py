import logging
import datetime
import base64
import re
import unicodedata
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional, Tuple
from .logging_utils import log_event

logger = logging.getLogger(__name__)
STOPWORDS_NOME = {"A", "O", "AS", "OS", "DE", "DA", "DO", "DAS", "DOS", "E"}


def _executar_etapa(nome_etapa: str, acao):
    try:
        return acao()
    except Exception as exc:
        raise RuntimeError(f"[ETAPA:{nome_etapa}] {exc}") from exc


def _normalizar_nome(texto: str) -> str:
    base = unicodedata.normalize("NFD", texto or "")
    base = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
    base = re.sub(r"[^A-Za-z0-9\s]", " ", base).upper()
    return re.sub(r"\s+", " ", base).strip()


def _tokens_nome(texto_normalizado: str) -> List[str]:
    tokens = [t for t in texto_normalizado.split() if t not in STOPWORDS_NOME and len(t) > 2]
    return tokens or texto_normalizado.split()


def _score_nome_proximidade(alvo: str, candidato: str) -> int:
    alvo_n = _normalizar_nome(alvo)
    cand_n = _normalizar_nome(candidato)
    if not alvo_n or not cand_n:
        return 0
    if alvo_n == cand_n:
        return 100
    if alvo_n in cand_n:
        return 95
    if cand_n in alvo_n:
        return 90

    tokens = _tokens_nome(alvo_n)
    if not tokens:
        return 0
    acertos = sum(1 for t in tokens if t in cand_n)
    ratio = acertos / len(tokens)
    bonus_inicio = 0.05 if cand_n.startswith(tokens[0]) else 0
    # Score fuzzy nunca deve superar um match exato (100).
    fuzzy = int((ratio + bonus_inicio) * 100)
    return min(fuzzy, 99)


def _escolher_indice_nome_mais_proximo(alvo: str, nomes_encontrados: List[str]) -> Tuple[Optional[int], int]:
    if not nomes_encontrados:
        return None, 0
    melhor_idx = 0
    melhor_score = -1
    for idx, nome in enumerate(nomes_encontrados):
        score = _score_nome_proximidade(alvo, nome)
        if score > melhor_score:
            melhor_idx = idx
            melhor_score = score
    return melhor_idx, melhor_score


def perform_search(page: Any, url_base: str, alvo: str, usar_refine: bool) -> Dict[str, Any]:
    log_event(logger, logging.INFO, "inicio_busca", alvo=alvo, url_base=url_base, usar_refine=usar_refine)
    _executar_etapa("abrir_portal", lambda: page.goto(url_base, wait_until="networkidle"))

    try:
        page.get_by_role("button", name="acceptButtonLabel").click()
    except Exception:
        pass

    _executar_etapa(
        "abrir_cartao_consulta",
        lambda: page.locator("div:nth-child(10) > .flipcard > .flipcard-wrap > .card.card-back > .card-body").click(
            force=True
        ),
    )
    _executar_etapa("abrir_consulta_pf", lambda: page.locator("#button-consulta-pessoa-fisica").click())

    input_busca = page.get_by_role("searchbox", name="Busque por Nome, Nis ou CPF (")
    _executar_etapa("focar_campo_busca", lambda: input_busca.click())
    _executar_etapa("preencher_busca", lambda: input_busca.fill(alvo))

    if usar_refine:
        log_event(logger, logging.INFO, "fluxo_refinado")
        refine_button = page.get_by_role("button", name="Refine a Busca")
        def abrir_refine_busca():
            try:
                refine_button.click(timeout=5000)
            except Exception:
                refine_button.click(force=True, timeout=5000)

        _executar_etapa("abrir_refine_busca", abrir_refine_busca)

        # O label pode aparecer com variação de texto ou estar fora da área visível.
        # Marcamos direto o checkbox com fallback forçado/JS para evitar timeout intermitente.
        def marcar_filtro_beneficiario():
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

        _executar_etapa("marcar_filtro_beneficiario", marcar_filtro_beneficiario)
        _executar_etapa("executar_consulta_refinada", lambda: page.locator("#btnConsultarPF").click())
    else:
        log_event(logger, logging.INFO, "fluxo_simples")
        _executar_etapa(
            "clicar_lupa_busca",
            lambda: page.locator('button[aria-label^="Enviar dados do formulário de busca"]').click(),
        )

    _executar_etapa("aguardar_carregamento_resultados", lambda: page.wait_for_load_state("networkidle"))
    contador_locator = page.locator("#countResultados")
    _executar_etapa("aguardar_contador_resultados", lambda: contador_locator.wait_for(state="visible", timeout=15000))

    _executar_etapa(
        "aguardar_contador_preenchido",
        lambda: page.wait_for_function("document.querySelector('#countResultados').innerText.trim() !== ''"),
    )
    quantidade_texto = contador_locator.inner_text().strip()
    quantidade = int(quantidade_texto.replace('.', '')) if quantidade_texto else 0
    log_event(logger, logging.INFO, "resultados_encontrados", quantidade=quantidade)

    indice_escolhido = 0
    if quantidade > 0:
        links_nomes = page.locator(".link-busca-nome")
        if any(ch.isdigit() for ch in alvo):
            log_event(logger, logging.INFO, "comparacao_nome_pulada", motivo="consulta_por_digitos")
        else:
            total_links = links_nomes.count()
            nomes_encontrados: List[str] = []
            for i in range(total_links):
                try:
                    nomes_encontrados.append(links_nomes.nth(i).inner_text().strip())
                except Exception:
                    nomes_encontrados.append("")
            idx_melhor, score_melhor = _escolher_indice_nome_mais_proximo(alvo, nomes_encontrados)
            if idx_melhor is None:
                log_event(logger, logging.WARNING, "nome_proximo_indefinido_fallback_primeiro", alvo=alvo)
                indice_escolhido = 0
            else:
                indice_escolhido = idx_melhor
                log_event(
                    logger,
                    logging.INFO,
                    "nome_mais_proximo_selecionado",
                    alvo=alvo,
                    indice=indice_escolhido,
                    score=score_melhor,
                    nome=nomes_encontrados[indice_escolhido],
                )

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

    # Seleciona o resultado escolhido quando houver.
    _executar_etapa(
        "abrir_resultado_escolhido",
        lambda: page.locator(".link-busca-nome").nth(indice_escolhido).click(),
    )
    return {"zero": False, "quantidade": quantidade}
