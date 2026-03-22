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

## Restrições e considerações
- Sem intervenção manual durante a execução normal; falhas devem ser sinalizadas via log/retorno.
- A automação depende da disponibilidade e layout do Portal da Transparência; mudanças podem exigir atualização de seletores.
- O uso de dados pessoais deve seguir políticas internas e LGPD (armazenamento transitório, mínimo necessário).
- Limite de 3 entradas por requisição (batch) e até 3 execuções paralelas para evitar sobrecarga (configurável via `BOT_MAX_WORKERS`).
- Validação prévia de CPF/NIS/nomes; entradas inválidas são rejeitadas sem abrir navegador; logs mascaram identificadores.

## Diretrizes de qualidade da entrega
| Eixo | Evidência esperada na solução |
|------|-------------------------------|
| Confiabilidade operacional | Execução estável dos fluxos principais, cobertura dos cenários de sucesso/erro e evidências em Base64 por execução. |
| Qualidade técnica | Código modular (navegação, extração, validação e API), tratamento explícito de erros e manutenção facilitada. |
| Integração ponta a ponta | Orquestração com Make e persistência estruturada em Google Drive/Sheets quando o fluxo externo estiver habilitado. |
| Segurança e acesso | Autenticação por token, gestão de segredos por ambiente e validação de entrada antes de abrir navegador. |
| Observabilidade | Logs de execução/falha com rastreabilidade por etapa, `id_consulta` e metadados de auditoria. |
| Documentação operacional | README e documentos `doc/` alinhados com contrato da API, execução local/cloud e evidências de integração. |

## Cenários de testes validados
| Cenário | Entrada | Saída esperada |
|---------|---------|----------------|
| Sucesso (CPF) | CPF ou NIS válido | JSON com dados coletados e evidência da tela. |
| Erro (CPF) | CPF ou NIS inexistente | JSON com mensagem de erro: "Não foi possível retornar os dados no tempo de resposta solicitado". |
| Sucesso (Nome) | Nome completo | JSON com dados do registro mais próximo por score de nome + evidência. |
| Erro (Nome) | Nome inexistente | JSON com mensagem de erro: "Foram encontrados 0 resultados para o termo …". |
| Filtrado | Sobrenome + filtro social | JSON com dados do registro mais próximo por score de nome + evidência. |

## Contrato de resposta da API
- **Consulta única com sucesso (`200`)**: retorna objeto raiz com `pessoa`, `beneficios` e `meta`.
- **Consulta única sem resultado de negócio (`200`)**: retorna `status="error"`, `error`, `beneficios=[]` e `meta` com evidência em Base64.
- **Lote (`200`)**: retorna `resultados[]`, cada item com `consulta`, `status` (`ok`, `invalid` ou `error`) e `resultado`/`error`.
- **Erros de protocolo/autenticação**:
  - `400`: payload inválido, entrada inválida ou limite excedido.
  - `401`: token ausente, inválido ou expirado.
  - `403`: escopo insuficiente.
  - `500`: falha inesperada no processamento.

## Exemplos de payload (consulta)
- **Consulta unitária simples**: `{"consulta": "04031769644", "refinar_busca": false}`
- **Consulta dupla simples**: `{"consultas": ["04031769644", "A ANNE CHRISTINE SILVA RIBEIRO"], "refinar_busca": false}` (máx. 3 entradas)
- **Consulta tripla simples**: `{"consultas": ["04031769644", "A ANNE CHRISTINE SILVA RIBEIRO", "A LIDA PEREIRA FIALHO"], "refinar_busca": false}` (máx. 3 entradas)
- **Consulta unitária avançada**: `{"consulta": "04031769644", "refinar_busca": true}`
- **Consulta dupla avançada**: `{"consultas": ["04031769644", "A ANNE CHRISTINE SILVA RIBEIRO"], "refinar_busca": true}` (máx. 3 entradas)
- **Consulta tripla avançada**: `{"consultas": ["04031769644", "A ANNE CHRISTINE SILVA RIBEIRO", "A LIDA PEREIRA FIALHO"], "refinar_busca": true}` (máx. 3 entradas)

## Decisões de implementação deste projeto
- Autenticação adotada: Bearer token JWT HS256 com `API_MASTER_KEY` dedicada.
- Configuração por variáveis de ambiente para API e bot, com descrição funcional centralizada no [README (Referência de variáveis de ambiente)](../README.md#env-reference).
- Batch com até 3 entradas por requisição; paralelismo operacional configurável por ambiente via `BOT_MAX_WORKERS` (reduza para `1` em produção se precisar de mais estabilidade).
- Nome de campo de API padronizado para `refinar_busca` (campo único aceito para refinamento).
