## Requisitos técnicos
- Backend em Python usando Django para disponibilizar o robô como API (recebe parâmetros e retorna JSON).
- Automação de navegação com Playwright (Chrome/Chromium headless).
- Validação de CPF e NIS antes da abertura do navegador para economizar recursos computacionais.
- Algoritmo de score de similaridade para nome (normalização + comparação) para selecionar o resultado mais próximo quando houver múltiplos registros.
- Geração de evidência (screenshot) convertida para Base64 e embutida na resposta.
- Estrutura de resposta em JSON contendo panorama, detalhes de benefícios e imagem.
- Logs de execução e falhas registrados pelo serviço Django.
- Execução em modo headless com suporte a execuções simultâneas.
- API online deve ter documentação técnica (Swagger/OpenAPI), incluindo autenticação, payloads e exemplos de resposta.
- Uso de chaves de acesso/segredos por variáveis de ambiente para integração entre API e cenário de automação no Make.

## Requisitos funcionais (MoSCoW)
| ID | Descrição | Prioridade (MoSCoW) |
|----|-----------|----------------------|
| RF-01 | Acessar o Portal da Transparência e navegar até “Pessoas Físicas e Jurídicas”. | Must (Alto) |
| RF-02 | Inserir parâmetros de busca (obrigatório: CPF, nome ou NIS; opcional: beneficiário de programa social) e executar a consulta. | Must (Alto) |
| RF-03 | Coletar dados exibidos na tela “Pessoa Física - Panorama da relação da pessoa com o Governo Federal”. | Must (Alto) |
| RF-04 | Capturar imagem da tela como evidência e convertê-la para Base64. | Must (Alto) |
| RF-05 | Para cada benefício (Auxílio Brasil, Auxílio Emergencial, Bolsa Família), acessar detalhes e extrair informações. | Must (Alto) |
| RF-06 | Encerrar a automação e retornar JSON com dados coletados e a imagem Base64. | Must (Alto) |
| RF-07 | Validar CPF e NIS antes da consulta no portal, rejeitando entradas inválidas sem abrir navegador. | Must (Alto) |
| RF-08 | Quando a consulta for por nome e houver múltiplos resultados, calcular score de proximidade e selecionar o nome mais aderente; sem aderência mínima, usar fallback para o primeiro resultado. | Must (Alto) |
| RF-09 | Publicar o JSON estruturado da execução em pasta controlada no Google Drive para auditoria. | Should (Médio) |
| RF-10 | Registrar os dados consolidados da execução em planilha estruturada no Google Sheets. | Should (Médio) |
| RF-11 | Orquestrar o fluxo ponta a ponta em hiperautomação no Make (entrada, chamada da API, gravação em Drive/Sheets e retorno de status). | Should (Médio) |
| RF-12 | Expor métricas operacionais da API em endpoint compatível com Prometheus (`/metrics`) para coleta e acompanhamento. | Could (Baixo) |
| RF-13 | Disparar notificação de alerta operacional via Grafana (ex.: Telegram) a partir de regras configuradas de observabilidade. | Could (Baixo) |

## Restrições e considerações
- Sem intervenção manual durante a execução normal; falhas devem ser sinalizadas via log/retorno.
- A automação depende da disponibilidade e layout do Portal da Transparência; mudanças podem exigir atualização de seletores.
- O uso de dados pessoais deve seguir políticas internas e LGPD (armazenamento transitório, mínimo necessário).
- A requisição em lote aceita de `1..N` entradas; quando o volume excede o paralelismo configurado, as consultas excedentes entram em fila interna e são processadas progressivamente no mesmo request.
- Paralelismo padrão do bot async: `1` browser fixo e até `4` consultas por abas (configurável via `BOT_MAX_CONSULTAS_POR_BROWSER`).
- Validação prévia de CPF/NIS/nomes; entradas inválidas são rejeitadas sem abrir navegador; logs mascaram identificadores.

## Diretrizes de qualidade da entrega
| Eixo | Evidência esperada na solução |
|------|-------------------------------|
| Confiabilidade operacional | Execução estável dos fluxos principais, cobertura dos cenários de sucesso/erro e evidências em Base64 por execução. |
| Qualidade técnica | Código modular (navegação, extração, validação e API), tratamento explícito de erros e manutenção facilitada. |
| Integração ponta a ponta | Orquestração com Make e persistência estruturada em Google Drive/Sheets quando o fluxo externo estiver habilitado. |
| Segurança e acesso | Autenticação por token, gestão de segredos por ambiente e validação de entrada antes de abrir navegador. |
| Observabilidade | Logs de execução/falha com rastreabilidade por etapa, `id_consulta`, métricas Prometheus, dashboards Grafana e alerta via Telegram (validados em ambiente local). |
| Documentação operacional | README e documentos `doc/` alinhados com contrato da API, execução local/cloud e evidências de integração. |

Nota de escopo de infraestrutura (desafio):
- A stack de observabilidade (`Prometheus + Grafana + alertas Telegram`) foi validada e está funcionando localmente.
- Esta stack não foi mantida em cloud nesta fase para evitar custo recorrente desnecessário no contexto do desafio.

## Cenários de testes validados
| Cenário | Entrada | Saída esperada |
|---------|---------|----------------|
| Sucesso (CPF) | CPF ou NIS válido | JSON com dados coletados e evidência da tela. |
| Sem resultado (CPF) | CPF ou NIS inexistente | JSON com `status="not_found"` e mensagem: "Não foi possível retornar os dados no tempo de resposta solicitado". |
| Sucesso (Nome) | Nome completo | JSON com dados do registro mais próximo por score de nome + evidência. |
| Sem resultado (Nome) | Nome inexistente | JSON com `status="not_found"` e mensagem: "Foram encontrados 0 resultados para o termo …". |
| Filtrado | Sobrenome + filtro social | JSON com dados do registro mais próximo por score de nome + evidência. |

## Contrato de resposta da API
- **Consulta única com sucesso (`200`)**: retorna objeto raiz com `pessoa`, `beneficios` e `meta`.
- **Consulta única sem resultado de negócio (`200`)**: retorna `status="not_found"`, `pessoa` com `N/A`, `beneficios=[]` e `meta` com mensagem/evidência.
- **Lote (`200`, `207` ou `502`)**: retorna `resultados[]`, cada item com `consulta`, `status` (`ok`, `not_found`, `invalid` ou `error`) e `resultado`/`error`.
- **Erros de protocolo/autenticação**:
  - `400`: payload inválido, lista vazia ou entrada inválida.
  - `401`: token ausente, inválido, expirado ou reutilizado (uso único).
  - `403`: escopo insuficiente.
  - `500`: falha inesperada no processamento.

## Exemplos de payload (consulta)
- Use `consulta` para requisição unitária e `consultas` para lote (`1..N` entradas).
- **Consulta unitária simples (CPF)**: `{"consulta": "04031769644", "refinar_busca": false}`
- **Consulta unitária simples (nome)**: `{"consulta": "GAABI OLIVEIRA DE MESQUITA", "refinar_busca": false}`
- **Consulta em lote simples**: `{"consultas": ["GAABI OLIVEIRA DE MESQUITA", "HAABE OLIVEIRA DA SILVA", "D ANGELA ALVES DE BARROS FELIPE", "I DINA APARECIDA DA SILVA GARCIA"], "refinar_busca": false}`
- **Consulta unitária avançada**: `{"consulta": "GAABI OLIVEIRA DE MESQUITA", "refinar_busca": true}`
- **Consulta em lote avançada**: `{"consultas": ["GAABI OLIVEIRA DE MESQUITA", "HAABE OLIVEIRA DA SILVA", "D ANGELA ALVES DE BARROS FELIPE", "I DINA APARECIDA DA SILVA GARCIA"], "refinar_busca": true}`
- **Consulta em lote gigante (12 itens, sem evidências Base64)**: `{"consultas": ["A DILA DA SILVA BRITO LIMA", "BA N TCHI OLIVE CONFORTE N DAH KOUAGOU", "CAA SANTOS BARROS MACHADO", "D ANGELA ALVES DE BARROS FELIPE", "E DILA LARISSA RODRIGUES BERTOLDO", "F MAGNIFICAT ZINSOU", "GAABI OLIVEIRA DE MESQUITA", "HA MOHAMMAD OLIUR RAHMAN", "HAABE OLIVEIRA DA SILVA", "I DINA APARECIDA DA SILVA GARCIA", "J QUECEMIRA BATISTA DOS SANTOS", "K TIANA MARLEN SILVA ARAUJO"], "refinar_busca": true, "incluir_base64": false}`
- **Consulta leve (sem evidências Base64)**: `{"consulta": "HAABE OLIVEIRA DA SILVA", "refinar_busca": true, "incluir_base64": false}`

## Decisões de implementação deste projeto
- Autenticação adotada: Bearer token JWT HS256 com `API_MASTER_KEY` dedicada e **uso único por consulta**.
- Configuração por variáveis de ambiente para API e bot, com descrição funcional centralizada no [README (Referência de variáveis de ambiente)](../README.md#env-reference).
- Batch com fila interna para excedentes; paralelismo operacional configurável por ambiente via `BOT_MAX_CONSULTAS_POR_BROWSER` (browser fixo em 1).
- Nome de campo de API padronizado para `refinar_busca` (campo único aceito para refinamento).
