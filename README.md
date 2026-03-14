# most-rpa-hyperautomation

Automação RPA/hiperautomação em Python que consulta o Portal da Transparência (consulta “Pessoas Físicas e Jurídicas”), extrai panorama e detalhes de benefícios sociais (Auxílio Brasil, Bolsa Família, Auxílio Emergencial), captura evidências em Base64 e retorna tudo em JSON.

Principais modos de uso:
- **API Django/DRF**: endpoint REST que executa o bot (batch ou single) e entrega JSON.
- **Runner local**: script `main.py` para execuções em lote gravando resultados em `output/`.

## Stack e componentes
- Playwright (Python) para navegação e scraping.
- Django + Django REST Framework + drf-spectacular para expor o robô como API e documentação Swagger (`/api/docs/`).
- Bot core em `bot/scraper.py` (usa `bot/navigation.py` e `bot/extraction.py`).
- `main.py` para executar múltiplos alvos em paralelo (ThreadPoolExecutor) e salvar JSONs em `output/`.

## Requisitos
- Python 3.10+ (testado em Linux)
- `pip install -r requirements.txt`
- Browsers do Playwright instalados: `playwright install`  
  (em Linux headless pode precisar de libs do Chromium: `libnss3`, `libatk1.0-0`, `libgtk-3-0`, etc.)

## Instalação rápida
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install
cp example.env .env   # ajuste os valores reais
```

## Executar como API (Django)
```bash
python manage.py runserver 8000
```
- Documentação interativa (Swagger): `http://127.0.0.1:8000/api/docs/`
- Esquema OpenAPI (YAML/JSON): `http://127.0.0.1:8000/api/schema/`
- Autorização: obtenha um token de acesso em `POST /api/token/` enviando sua `api_key`; use o token retornado no header `Authorization: Bearer <token>`. Tokens expiram após o TTL configurado.

### Autenticação
- Obtenha um **JWT** curto em `POST /api/token/` enviando `{"api_key": "<sua-chave>"}` (configurada em `.env` via `API_MASTER_KEY`).
- Use o token retornado no header `Authorization: Bearer <token>` ao chamar `/api/consulta/`. Tokens são assinados com HS256 e expiram após `API_TOKEN_TTL` segundos.

### Endpoint principal
`POST /api/consulta/`

Payloads aceitos:
- **Single**: `{"consulta": "04031769644", "refine": false}`
- **Batch simples**: `{"consultas": ["04031769644", "12345678901"], "refine": false}` (máx. 3 entradas)
- **Batch avançado**: `{"itens": [{"consulta": "04031769644"}, {"consulta": "12345678901", "refine": false}]}` (máx. 3 itens; `refine` padrão = true)

Respostas seguem o JSON do bot (pessoa, benefícios, meta). Em caso de erro, retorna `{ "status": "error", "error": "..." }`.

## Executar via runner local
Edite a lista `lista_alvos` em `main.py` e rode:
```bash
python main.py
```
Cada alvo gera um `output/result_<alvo>_<timestamp>.json`. Limite sugerido: até 3 alvos por execução.

## Parâmetros importantes
- `TransparencyBot(headless=True, alvo="CPF|NIS|Nome", usar_refine=False)` — passe o alvo na criação do bot.
- `usar_refine=True` ativa o fluxo “Refine a Busca”; `False` usa a busca simples (lupa).

## Estrutura de saída (resumo)
- `pessoa`: `nome`, `cpf`, `localidade`, `quantidade_beneficios`…
- `beneficios`: lista com `tipo`, `nis`, `valor_recebido`, `detalhe_href`, `detalhe_evidencia` (Base64), `parcelas` (itens das tabelas de detalhe).
- `meta`: `resultados_encontrados`, `beneficios_encontrados`, `panorama_relacao` (Base64), `data_consulta`, `hora_consulta`.

## Boas práticas e troubleshooting
- Se o Chromium não subir, reinstale deps do sistema e rode `playwright install`.
- Site pode mudar layout; seletores estão em `bot/navigation.py` e `bot/extraction.py`.
- Logs em `bot_execution.log` (runner) e via logging Django no endpoint.

## Segurança
Uso apenas para fins legais; trate dados pessoais conforme LGPD. Armazene resultados de forma transitória ou conforme política interna.
