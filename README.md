# most-rpa-hyperautomation

Uma automação de raspagem com Playwright (Python) para consultar o Portal da Transparência do Governo Federal e extrair informações sobre benefícios sociais (por exemplo: Auxílio Brasil, Bolsa Família, Auxílio Emergencial). O projeto captura evidências (screenshots em Base64) e gera um JSON estruturado com os resultados.

**Principais componentes:** código do bot em [bot/scraper.py](bot/scraper.py), um simples runner em `main.py` e uma pasta `output/` para gravar resultados.

**Status:** funcional para consultas individuais; opções para execução em lote via `main.py`.

## Recursos

- Playwright (Python) para controle de navegador e extração robusta de SPAs.
- Captura de evidência em Base64 embutida no JSON de saída.
- Detecção e extração de tabelas de detalhe para diferentes benefícios.
- Configurações para `headless`, fuso-horário e user-agent.

## Requisitos

- Python 3.10+ (testado em Linux)
- Virtualenv (recomendado)
- Dependências Python listadas em `requirements.txt`
- Playwright browsers instalados (`playwright install`)

## Instalação rápida

1. Criar e ativar um ambiente virtual

```bash
python -m venv venv
source venv/bin/activate
```

2. Instalar dependências

```bash
pip install -r requirements.txt
```

3. Instalar browsers do Playwright

```bash
playwright install
```

OBS: Em distribuições Linux sem interface, pode ser necessário instalar bibliotecas do sistema para o Chromium (por exemplo: `libnss3`, `libatk1.0-0`, `libgtk-3-0`, etc.).

## Uso

Há duas formas comuns de usar o bot:

- Via `main.py` (execução em lote ou runner fornecido).
- Importando `TransparencyBot` e executando manualmente.

Exemplo mínimo para testar diretamente no REPL ou num script:

```python
from bot.scraper import TransparencyBot
import json

bot = TransparencyBot(headless=True)
bot.alvo = "04031769644"  # CPF ou NIS ou Nome
resultado = bot.run()
print(json.dumps(resultado, ensure_ascii=False, indent=2))
```

Para rodar `main.py`, abra e ajuste a lista de alvos conforme necessário, então execute:

```bash
python main.py
```

Os resultados podem ser gravados em `output/` dependendo de como `main.py` está implementado.

## Configuração e parâmetros relevantes

- `TransparencyBot(headless: bool = True)` — executar em modo headless por padrão.
- `bot.alvo` — string com CPF, NIS ou nome para busca.
- `bot.usar_refine` — `True` para busca refinada (fluxo alternativo), `False` para busca simples (lupa).

Se desejar parametrizar via CLI, crie um wrapper simples em `main.py` que aceite argumentos e instancie `TransparencyBot` dinamicamente.

## Estrutura de saída (resumo)

O JSON retornado segue um formato aproximado:

- `pessoa`: metadados (`nome`, `cpf`, `localidade`, `nis`)
- `beneficios`: lista de objetos com `tipo`, `nis`, `valor_recebido`, `detalhe_href`, `detalhe_evidencia` (Base64) e `parcelas` (lista de registros)
- `meta`: dados da execução (`resultados_encontrados`, `beneficios_encontrados`, `data_consulta`, `hora_consulta`)

Exemplo (resumido):

```json
{
  "pessoa": { "nome": "...", "cpf": "..." },
  "beneficios": [ { "tipo": "Auxílio Brasil", "parcelas": [...] } ],
  "meta": { "data_consulta": "12/03/2026" }
}
```

## Troubleshooting

- Se o Playwright falhar ao lançar o Chromium em Linux, verifique dependências do sistema e execute `playwright install` novamente.
- Se encontrar bloqueios anti-bot, `bot/scraper.py` já tenta mascarar automação (user-agent, desativar webdriver, args como `--disable-blink-features=AutomationControlled`). Ajustes adicionais podem ser necessários dependendo do ambiente.
- Timeout de seletores: aumente os tempos (`wait_for_selector`, `wait_for_timeout`) se a conexão estiver lenta.

## Segurança e ética

Use este projeto apenas para fins legais e éticos. Respeite termos de uso do site alvo e a legislação local sobre proteção de dados.

## Contribuição

Pull requests são bem-vindos. Para mudanças maiores, abra uma issue descrevendo a proposta.

## Licença

Este repositório não especifica uma licença. Adicione uma licença apropriada se pretende compartilhar publicamente.

---

Arquivo principal do bot: [bot/scraper.py](bot/scraper.py)