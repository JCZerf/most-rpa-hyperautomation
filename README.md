# Most RPA Hyperautomation - Transparency Scraper

Pequeno projeto para extrair dados do Portal da Transparência usando Playwright.

## Pré-requisitos

- Python 3.8+ (venv recomendado)
- Dependências no `requirements.txt`
- Playwright browsers instalados

## Instalação rápida

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Instala navegadores do Playwright
playwright install
```

## Execução

O script principal é `main.py`. Ele executa o bot e grava um JSON com os dados extraídos em `output/`.

```bash
python main.py
```

Por padrão o bot roda com `headless=False` (abre janela). Para rodar em background, altere `TransparencyBot(headless=False)` para `TransparencyBot(headless=True)` em `main.py`.

## Arquivo de saída

O arquivo gerado fica em `output/` com o nome formatado como: `nome_cpf_localidade.json` (partes foram sanitizadas; `cpf` fica apenas com dígitos).

Exemplo:

```
output/A_ANNE_CHRISTINE_SILVA_RIBEIRO_734995_PROPIA-SE.json
```