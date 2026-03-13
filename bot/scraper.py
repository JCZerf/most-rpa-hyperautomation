import json
import logging
import datetime
import base64
from zoneinfo import ZoneInfo
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TransparencyBot:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.url_base = "https://portaldatransparencia.gov.br/"
        self.alvo = "04031769644"
        #04031769644
        #A LIDA PEREIRA FIALHO
        # PARAMETRO OPCIONAL: True para usar busca refinada, False para busca simples (Lupa)
        self.usar_refine = False 
        
    def run(self) -> Dict[str, Any]:
        with sync_playwright() as pw:
            # 1. Desativar a flag de automação via argumentos
            browser = pw.chromium.launch(
                headless=self.headless, 
                slow_mo=500,
                args=[
                    "--disable-blink-features=AutomationControlled", # Esconde que é automação
                    "--no-sandbox"
                ]
            )
            
            # 2. Criar um contexto com User-Agent e linguagens humanas
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720},
                locale="pt-BR",
                timezone_id="America/Sao_Paulo"
            )
            page = context.new_page()
            # inicializa variáveis que podem não ser definidas em todos os fluxos
            nis = None

            # 3. Pequeno script para limpar vestígios de bot no JS da página
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            try:
                # --- Navegação e Busca ---
                logger.info(f"Iniciando busca para: {self.alvo}")
                page.goto(self.url_base, wait_until="networkidle")
                
                # Aceitar cookies
                page.get_by_role("button", name="acceptButtonLabel").click()
                
                # Atalho para Consulta Pessoa Física
                page.locator("div:nth-child(10) > .flipcard > .flipcard-wrap > .card.card-back > .card-body").click(force=True)
                page.locator("#button-consulta-pessoa-fisica").click()

                # Preenchimento do campo obrigatório
                input_busca = page.get_by_role("searchbox", name="Busque por Nome, Nis ou CPF (")
                input_busca.click()
                input_busca.fill(self.alvo)
               
                # --- LÓGICA DE BUSCA HÍBRIDA ---
                if self.usar_refine:
                    logger.info("Fluxo: Busca Refinada selecionado.")
                    page.get_by_role("button", name="Refine a Busca").click()
                    page.locator("#box-busca-refinada").get_by_text("Beneficiário de Programa").click()
                    # Clica no botão 'Consultar' (ID específico do refine)
                    page.locator("#btnConsultarPF").click()
                else:
                    logger.info("Fluxo: Busca Simples (Lupa) selecionado.")
                    # Clica no botão da Lupa (submit do formulário)
                    page.locator('button[aria-label^="Enviar dados do formulário de busca"]').click()

                page.wait_for_load_state("networkidle")
                # --- Validação dos Resultados ---
                contador_locator = page.locator("#countResultados")
                contador_locator.wait_for(state="visible", timeout=15000)
                
                page.wait_for_function("document.querySelector('#countResultados').innerText.trim() !== ''")
                
                quantidade_texto = contador_locator.inner_text().strip()
                quantidade = int(quantidade_texto.replace('.', '')) if quantidade_texto else 0
                logger.info(f"Resultados encontrados: {quantidade}")

                # Se houver resultados, verificamos se o primeiro resultado contém o nome buscado
                if quantidade > 0:
                    primeiro_resultado_nome = page.locator(".link-busca-nome").first.inner_text().strip().upper()
                    # Se o termo buscado contém dígitos (provavelmente CPF ou NIS), não compare com o nome
                    if any(ch.isdigit() for ch in self.alvo):
                        logger.info("Termo contém dígitos; pulando verificação por nome (busca por NIS/CPF).")
                    else:
                        # Se o nome no site não tem nada a ver com o alvo, tratamos como 0 resultados reais
                        if self.alvo.upper() not in primeiro_resultado_nome:
                            logger.warning(f"Resultados genéricos detectados ({primeiro_resultado_nome}). Tratando como não encontrado.")
                            quantidade = 0

                # Tratamento especial: se não houver resultados, captura evidência e retorna JSON
                if quantidade == 0:
                    logger.info("Nenhum resultado encontrado para o termo; capturando evidência e retornando.")
                    agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
                    data_consulta = agora.strftime("%d/%m/%Y")
                    hora_consulta = agora.strftime("%H:%M")
                    evidencia_bytes = page.screenshot(full_page=True)
                    evidencia_base64 = base64.b64encode(evidencia_bytes).decode("utf-8")

                    resultado_final = {
                        "pessoa": {"consulta": self.alvo},
                        "beneficios": [],
                        "meta": {
                            "resultados_encontrados": quantidade,
                            "evidencia_resultados_zero": evidencia_base64,
                            "data_consulta": data_consulta,
                            "hora_consulta": hora_consulta
                        }
                    }
                    logger.info(f"Processamento concluído: nenhum resultado para termo {self.alvo}.")
                    return resultado_final

                # Seleção do resultado
                page.locator(".link-busca-nome").first.click()

                # --- Extração de Dados Cadastrais ---
                nome = page.locator("div.col-sm-4:has(strong:has-text('Nome')) span").inner_text().strip()
                cpf = page.locator("div.col-sm-3:has(strong:has-text('CPF')) span").inner_text().strip()
                localidade = page.locator("div.col-sm-3:has(strong:has-text('Localidade')) span").inner_text().strip()

                # --- Fluxo do Acordeão e Detalhamento ---
                botao_acordeon = page.get_by_role("button", name="Recebimentos de recursos")
                botao_acordeon.scroll_into_view_if_needed()
                botao_acordeon.dispatch_event("click")

                btn_detalhar = page.locator("a:text('Detalhar')").first
                
                try:
                    btn_detalhar.wait_for(state="visible", timeout=8000)
                except:
                    logger.warning("Botão detalhar não apareceu, tentando clique forçado no acordeão...")
                    botao_acordeon.click(force=True)
                    btn_detalhar.wait_for(state="visible", timeout=5000)

                # Captura de evidência: Panorama (base64)
                panorama_bytes = page.screenshot(full_page=True)
                panorama_base64 = base64.b64encode(panorama_bytes).decode("utf-8")
                logger.info("Panorama capturado em base64.")    

                # Verifica existência de benefícios relevantes
                beneficios_possiveis = ["Auxílio Brasil", "Auxílio Emergencial", "Bolsa Família"]

                beneficios_encontrados: List[str] = []
                for b in beneficios_possiveis:
                    if page.locator(f"strong:has-text('{b}')").count() > 0:
                        beneficios_encontrados.append(b)

                 # Se nenhum benefício relevante for encontrado, captura evidência e retorna JSON sem parcelas
                if not beneficios_encontrados:
                    logger.info("Nenhum benefício relevante encontrado. Montando JSON sem parcelas.")
                    agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
                    data_consulta = agora.strftime("%d/%m/%Y")
                    hora_consulta = agora.strftime("%H:%M")

                    resultado_final = {
                        "pessoa": {
                            "nome": nome,
                            "cpf": cpf,
                            "localidade": localidade,
                            "nis": nis
                        },
                        "beneficios": [],  # nenhum benefício dos três encontrados
                        "meta": {
                            "resultados_encontrados": quantidade,
                            "beneficios_encontrados": beneficios_encontrados,
                            "evidencia_sem_beneficio": panorama_base64,
                            "data_consulta": data_consulta,
                            "hora_consulta": hora_consulta
                        }
                    }
                    logger.info(f"Processamento concluído para {nome} (sem benefícios relevantes).")
                    return resultado_final

                # Há pelo menos um benefício relevante — percorre todos os blocos de benefício
                logger.info(f"Benefícios encontrados: {beneficios_encontrados}. Extraindo cada benefício presente no painel.")

                beneficios_resultado: List[Dict[str, Any]] = []
                # localiza todos os blocos .br-table dentro do acordeão de recebimentos
                blocos = page.locator("#accordion-recebimentos-recursos .br-table")
                for i in range(blocos.count()):
                    bloco = blocos.nth(i)
                    try:
                        tipo = bloco.locator("strong").inner_text().strip()
                    except Exception:
                        tipo = bloco.inner_text().strip().split('\n', 1)[0][:50]

                    # tenta extrair dados da primeira linha da tabela dentro do bloco
                    try:
                        cols = bloco.locator("table tbody tr td")
                        nis_texto = cols.nth(1).inner_text().strip() if cols.count() > 1 else ""
                        nis_benef = " ".join(nis_texto.split())
                        valor_recebido = cols.last.inner_text().strip() if cols.count() >= 4 else ""
                    except Exception:
                        nis_benef = None
                        valor_recebido = ""

                    # href do detalhe
                    try:
                        href = bloco.locator("tbody tr a").first.get_attribute("href")
                    except Exception:
                        href = None

                    detalhe_parcelas: List[Dict[str, str]] = []
                    detalhe_evidence_b64 = None

                    if href:
                        try:
                            # abre nova aba para o detalhe do benefício
                            detalhe_url = href if href.startswith("http") else self.url_base.rstrip("/") + href
                            nova_pagina = context.new_page()
                            nova_pagina.goto(detalhe_url, wait_until="networkidle")
                            try:
                                nova_pagina.wait_for_selector(".loading-grande", timeout=2000)
                                nova_pagina.wait_for_selector(".loading-grande", state="hidden", timeout=20000)
                            except Exception:
                                pass

                            # coleta parcelas se tabelas específicas existirem (mapeamento por benefício)
                            try:
                                # Bolsa Família - tabelaDetalheValoresRecebidos
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
                                # Auxílio Brasil - tabelaDetalheDisponibilizado (7 colunas)
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
                                # Auxílio Brasil - tabelaDetalheValoresSacados (mes folha, mes referencia, uf, municipio, valor_parcela)
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
                                    # Fallback genérico: tenta tabelaDetalheDisponibilizado ou qualquer tabela na página
                                    tabela = None
                                    if nova_pagina.locator("table#tabelaDetalheDisponibilizado").count():
                                        tabela = nova_pagina.locator("table#tabelaDetalheDisponibilizado")
                                    else:
                                        # pega primeira tabela com tbody tr
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
                                                # mapear dinamicamente dependendo do número de colunas
                                                row = [cols.nth(ci).inner_text().strip() for ci in range(cols.count())]
                                                detalhe_parcelas.append({f"col_{idx}": val for idx, val in enumerate(row)})
                            except Exception:
                                detalhe_parcelas = []

                            # captura evidência da tela de detalhe
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

                # Data e hora da consulta no fuso de São Paulo (dd/mm/aaaa e 24h HH:MM)
                agora = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
                data_consulta = agora.strftime("%d/%m/%Y")
                hora_consulta = agora.strftime("%H:%M")

                resultado_final = {
                    "pessoa": {
                        "nome": nome,
                        "cpf": cpf,
                        "localidade": localidade,
                    },
                    "beneficios": beneficios_resultado,
                    "meta": {
                        "resultados_encontrados": quantidade,
                        "beneficios_encontrados": beneficios_encontrados,
                        "panorama_relacao": panorama_base64,
                        "data_consulta": data_consulta,
                        "hora_consulta": hora_consulta
                    }
                }

                logger.info(f"Processamento concluído para {nome}.")
                return resultado_final

            except Exception as e:
                logger.error(f"Erro durante a execução do bot: {e}", exc_info=True)
                return {"error": str(e)}

            finally:
                try:
                    if 'context' in locals() and context:
                        context.close()
                except Exception:
                    logger.debug("Falha ao fechar context", exc_info=True)
                try:
                    if 'browser' in locals() and browser:
                        browser.close()
                except Exception:
                    logger.debug("Falha ao fechar browser", exc_info=True)