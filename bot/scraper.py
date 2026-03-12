import json
import logging
import datetime
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TransparencyBot:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.url_base = "https://portaldatransparencia.gov.br/"
        self.alvo = "04031769644"

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

                # Preenchimento e Refino
                page.get_by_role("searchbox", name="Busque por Nome, Nis ou CPF (").fill(self.alvo)
                page.get_by_role("button", name="Refine a Busca").click()
                page.locator("#box-busca-refinada").get_by_text("Beneficiário de Programa").click()
                page.get_by_role("button", name="Buscar os dados digitados").click()

                # --- Validação dos Resultados ---
                contador_locator = page.locator("#countResultados")
                contador_locator.wait_for(state="visible", timeout=15000)
                
                # Sincronismo inteligente: espera o texto carregar de fato
                page.wait_for_function("document.querySelector('#countResultados').innerText.trim() !== ''")
                
                quantidade_texto = contador_locator.inner_text().strip()
                quantidade = int(quantidade_texto.replace('.', '')) if quantidade_texto else 0
                logger.info(f"Resultados encontrados: {quantidade}")

                # Seleção do resultado
                page.locator(".link-busca-nome").first.click()

                # --- Extração de Dados Cadastrais ---
                # Usamos seletores específicos para garantir a captura correta
                nome = page.locator("div.col-sm-4:has(strong:has-text('Nome')) span").inner_text().strip()
                cpf = page.locator("div.col-sm-3:has(strong:has-text('CPF')) span").inner_text().strip()
                localidade = page.locator("div.col-sm-3:has(strong:has-text('Localidade')) span").inner_text().strip()

                # --- Fluxo do Acordeão e Detalhamento ---
                botao_acordeon = page.get_by_role("button", name="Recebimentos de recursos")
                botao_acordeon.scroll_into_view_if_needed()
                botao_acordeon.dispatch_event("click")

                btn_detalhar = page.locator("a:text('Detalhar')").first
                
                # Lógica de tentativa dupla para expansão do acordeão
                try:
                    btn_detalhar.wait_for(state="visible", timeout=8000)
                except:
                    logger.warning("Botão detalhar não apareceu, tentando clique forçado no acordeão...")
                    botao_acordeon.click(force=True)
                    btn_detalhar.wait_for(state="visible", timeout=5000)

                # Captura o valor total da tabela resumo
                valor_total = page.locator("table#tabela-visao-geral-sancoes tbody tr").first.locator("td").last.inner_text().strip()

                # Transição para a tela de Detalhes Mensais
                btn_detalhar.click(force=True)
                page.wait_for_load_state("networkidle")
                page.wait_for_selector(".loading-grande", state="hidden")
                
                # --- Extração das Parcelas com Mapeamento Completo ---
                tabela_detalhe = page.locator("table#tabelaDetalheDisponibilizado")
                
                # 1. Esperar que o primeiro TD da tabela contenha algum dígito (número do mês ou valor). Isso indica que a tabela não está mais vazia.
                tabela_detalhe.locator("tbody td").first.wait_for(
                    state="visible", 
                    timeout=15000
                )

                # 2. Pequena pausa para garantir que o DataTables terminou o desenho
                page.wait_for_timeout(1000)

                linhas_parcelas = tabela_detalhe.locator("tbody tr")
                detalhes_mensais: List[Dict[str, str]] = []

                logger.info(f"Iniciando mapeamento de {linhas_parcelas.count()} linhas...")

                for i in range(linhas_parcelas.count()):
                    cols = linhas_parcelas.nth(i).locator("td")
                    
                    #Mapeamento completo com validação de quantidade de colunas para evitar erros de indexação
                    if cols.count() >= 7:
                        detalhes_mensais.append({
                            "mes": cols.nth(0).inner_text().strip(),
                            "parcela": cols.nth(1).inner_text().strip(),
                            "uf": cols.nth(2).inner_text().strip(),
                            "municipio": cols.nth(3).inner_text().strip(),
                            "enquadramento": cols.nth(4).inner_text().strip(),
                            "valor": cols.nth(5).inner_text().strip(),
                            "observacao": cols.nth(6).inner_text().strip(),
                        })
                        # --- Lógica de Nome de Arquivo Dinâmico para Evidência ---
                nome_limpo = nome.replace(" ", "_").upper()
                cpf_limpo = cpf.replace(".", "").replace("-", "").replace("*", "")
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                
                nome_evidencia = f"{nome_limpo}_{cpf_limpo}_{ts}.png"
                caminho_evidencia = f"output/{nome_evidencia}"
                page.screenshot(path=caminho_evidencia, full_page=True)
                logger.info(f"Evidência visual salva: {caminho_evidencia}")       

                # --- Estruturação do Resultado ---
                resultado_final = {
                    "pessoa": {
                        "nome": nome,
                        "cpf": cpf,
                        "localidade": localidade,
                    },
                    "beneficios": [
                        {
                            "tipo": "Auxílio Emergencial",
                            "valor_total": valor_total,
                            "parcelas": detalhes_mensais,
                        }
                    ],
                    "meta": {
                        "resultados_encontrados": quantidade,
                        "arquivo_evidencia": nome_evidencia
                    }
                }
                
                logger.info(f"Processamento concluído para {nome}.")
                return resultado_final

            except Exception as e:
                logger.error(f"Erro durante a execução do bot: {e}")
                return {"error": str(e)}
            
            finally:
                context.close()
                browser.close()
