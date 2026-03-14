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
- Autorização: obtenha um token OAuth2 (client_credentials) em `POST /api/token/` enviando `client_id` e `client_secret`; use o token retornado no header `Authorization: Bearer <token>`. Tokens expiram após o TTL configurado (`API_TOKEN_TTL`).

### Autenticação (OAuth2 client_credentials simplificado)
- `POST /api/token/` com corpo `{"grant_type": "client_credentials", "client_id": "<ID>", "client_secret": "<SECRET>", "scope": "bot:read"}`. `client_id`/`client_secret` vêm do `.env` (`OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET`).
- Use o `access_token` retornado no header `Authorization: Bearer <token>` ao chamar `/api/consulta/`. Tokens HS256, `aud` configurado por `OAUTH_AUDIENCE`, expiram após `API_TOKEN_TTL` segundos.

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

## Testes
```bash
pytest
```
Os testes unitários cobrem validação de entrada e endpoints (`/api/token/`, `/api/consulta/`) com mocks para evitar abrir o navegador.

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

## Cenários de teste do desafio
Os cenários fornecidos pela MOST estão documentados em `doc/02-requisito-do-projeto.md` (seção “Cenários de teste”). A suíte `pytest` cobre os casos de sucesso/erro por CPF/NIS e Nome, além de cenário com parcelas e evidências.
