# Most RPA Hyperautomation - Transparency Portal Scraper 🚀

Projeto de automação robusta desenvolvido para extrair dados detalhados de beneficiários do Auxílio Emergencial diretamente do **Portal da Transparência do Governo Federal**. Esta solução foi projetada com foco em resiliência, contornando bloqueios de segurança e garantindo a integridade dos dados extraídos.

## 🛠️ Tecnologias e Técnicas Aplicadas

- **Playwright (Python):** Motor de automação de alta performance para interação com páginas dinâmicas.
- **Evasão de Detecção (Anti-Bot):** Implementação de técnicas avançadas para evitar CAPTCHAs e bloqueios de firewall, incluindo o mascaramento da flag `navigator.webdriver`, uso de User-Agents reais e emulação de fuso horário/localidade.
- **Mapeamento Estruturado:** Extração completa de 7 colunas de detalhes (Mês de Disponibilização, Parcela, UF, Município, Enquadramento, Valor e Observações).
- **Sincronismo de Dados:** Tratamento de latência e carregamento assíncrono (AJAX) para garantir que o bot não capture tabelas vazias.
- **Logging Profissional:** Monitoramento detalhado de cada etapa do processo via console e arquivo de log.
- **Evidência Visual:** Geração automática de screenshots da extração como prova de execução (audit trail).

## 📋 Pré-requisitos

- **Python 3.8+** (Recomendado Python 3.12)
- Navegador **Chromium** (gerenciado pelo Playwright)
- Ambiente Linux (Testado em Ubuntu/WSL) ou Windows

## 🚀 Instalação e Configuração

```bash
# 1. Criar o ambiente virtual e ativar
python -m venv venv
source venv/bin/activate  # No Windows use: venv\Scripts\activate

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Instalar o motor do navegador
playwright install chromium

🤖 Execução
Para iniciar a automação, execute o script principal:

Nota: Por padrão, o bot inicia com headless=False para visualização da interface. Para execução em background (servidores), altere a instância para TransparencyBot(headless=True) no arquivo main.py.

📂 Estrutura de Saída (Output)
O bot organiza os resultados na pasta output/ gerando os seguintes arquivos:

JSON de Dados: result_TIMESTAMP.json - Contém o perfil completo do beneficiário, metadados da busca e a lista detalhada de todas as parcelas encontradas.

Evidência Visual: evidencia_sucesso.png - Captura de tela da página de detalhamento, comprovando a veracidade dos dados extraídos.

Exemplo do JSON Gerado:
JSON

{
  "pessoa": {
    "nome": "A ANNE CHRISTINE SILVA RIBEIRO",
    "cpf": "***.734.995-**",
    "localidade": "PROPRIÁ - SE"
  },
  "beneficios": [
    {
      "tipo": "Auxílio Emergencial",
      "valor_total": "R$ 3.900,00",
      "parcelas": [
        {
          "mes": "12/2020",
          "parcela": "8",
          "uf": "BA",
          "municipio": "POJUCA",
          "enquadramento": "EXTRACAD",
          "valor": "300,00",
          "observacao": "NÃO HÁ"
        }
      ]
    }
  ],
  "meta": {
    "resultados_encontrados": 86
  }
}