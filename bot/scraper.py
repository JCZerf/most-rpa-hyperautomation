import json
import logging
from typing import Any, Dict, List
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


class TransparencyBot:
    def __init__(self, headless: bool = True):
        self.headless = headless

    def run(self) -> Dict[str, Any]:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless, slow_mo=500)
            context = browser.new_context()
            page = context.new_page()

            # Navegação e interações até o resultado
            page.goto("https://portaldatransparencia.gov.br/")
            page.get_by_role("button", name="acceptButtonLabel").click()
            page.locator("div:nth-child(10) > .flipcard > .flipcard-wrap > .card.card-back > .card-body").click(force=True)
            page.locator("#button-consulta-pessoa-fisica").click()
            page.get_by_role("searchbox", name="Busque por Nome, Nis ou CPF (").fill("A ANNE CHRISTINE SILVA RIBEIRO")
            page.get_by_role("button", name="Refine a Busca").click()
            page.locator("#box-busca-refinada").get_by_text("Beneficiário de Programa").click()
            page.get_by_role("button", name="Buscar os dados digitados").click()

            contador_locator = page.locator("#countResultados")
            contador_locator.wait_for(state="visible", timeout=15000)

            quantidade_texto = contador_locator.inner_text().strip()
            if not quantidade_texto:
                page.wait_for_timeout(2000)
                quantidade_texto = contador_locator.inner_text().strip()

            try:
                quantidade = int(quantidade_texto.replace('.', ''))
            except ValueError:
                quantidade = 0

            first_option = page.locator(".link-busca-nome").first
            first_option.click()

            # Captura dos dados da página de detalhes
            nome = page.locator("div.col-sm-4:has(strong:has-text('Nome')) span").inner_text()
            cpf = page.locator("div.col-sm-3:has(strong:has-text('CPF')) span").inner_text()
            localidade = page.locator("div.col-sm-3:has(strong:has-text('Localidade')) span").inner_text()

            # Abre acordeão
            botao_acordeon = page.get_by_role("button", name="Recebimentos de recursos")
            botao_acordeon.scroll_into_view_if_needed()
            botao_acordeon.dispatch_event("click")

            # Aguarda botão de detalhar
            btn_detalhar = page.locator("a:text('Detalhar')").first
            try:
                btn_detalhar.wait_for(state="visible", timeout=10000)
            except:
                botao_acordeon.click(force=True)
                btn_detalhar.wait_for(state="visible", timeout=5000)

            # Captura valor total
            valor_total = page.locator("table tbody tr").first.locator("td").last.inner_text().strip()

            # Vai para os detalhes
            btn_detalhar.click(force=True)
            page.wait_for_load_state("networkidle")
            page.wait_for_selector(".loading-grande", state="hidden")
            tabela_detalhe = page.locator("table#tabelaDetalheDisponibilizado")
            tabela_detalhe.wait_for(state="visible")

            linhas_parcelas = tabela_detalhe.locator("tbody tr")
            detalhes_mensais: List[Dict[str, str]] = []

            total_linhas = linhas_parcelas.count()
            for i in range(total_linhas):
                linha = linhas_parcelas.nth(i)
                if linha.locator("td").count() > 1:
                    mes = linha.locator("td").nth(0).inner_text().strip()
                    parcela_num = linha.locator("td").nth(1).inner_text().strip()
                    valor_parcela = linha.locator("td").nth(5).inner_text().strip()
                    detalhes_mensais.append({
                        "mes": mes,
                        "parcela": parcela_num,
                        "valor": valor_parcela,
                    })

            resultado_final: Dict[str, Any] = {
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
                    "resultados_encontrados": quantidade
                }
            }
            print(json.dumps(resultado_final, ensure_ascii=False, indent=2))
            context.close()
            browser.close()

            return resultado_final