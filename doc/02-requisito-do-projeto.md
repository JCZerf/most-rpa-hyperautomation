## Requisitos técnicos
- Backend em Python usando Django para disponibilizar o robô como API (recebe parâmetros e retorna JSON).
- Automação de navegação com Playwright (Chrome/Chromium headless).
- Geração de evidência (screenshot) convertida para Base64 e embutida na resposta.
- Estrutura de resposta em JSON contendo panorama, detalhes de benefícios e imagem.
- Logs de execução e falhas registrados pelo serviço Django.
- Execução em modo headless com suporte a execuções simultâneas.
- Se API online for disponibilizada, documentação via Swagger/OpenAPI é diferencial.

## Requisitos funcionais (MoSCoW)
| ID | Descrição | Prioridade (MoSCoW) |
|----|-----------|----------------------|
| RF-01 | Acessar o Portal da Transparência e navegar até “Pessoas Físicas e Jurídicas”. | Must (Alto) |
| RF-02 | Inserir parâmetros de busca (obrigatório: CPF, nome ou NIS; opcional: beneficiário de programa social) e executar a consulta. | Must (Alto) |
| RF-03 | Coletar dados exibidos na tela “Pessoa Física - Panorama da relação da pessoa com o Governo Federal”. | Must (Alto) |
| RF-04 | Capturar imagem da tela como evidência e convertê-la para Base64. | Must (Alto) |
| RF-05 | Para cada benefício (Auxílio Brasil, Auxílio Emergencial, Bolsa Família), acessar detalhes e extrair informações. | Must (Alto) |
| RF-06 | Encerrar a automação e retornar JSON com dados coletados e a imagem Base64. | Must (Alto) |

## Restrições e considerações
- Sem intervenção manual durante a execução normal; falhas devem ser sinalizadas via log/retorno.
- A automação depende da disponibilidade e layout do Portal da Transparência; mudanças podem exigir atualização de seletores.
- O uso de dados pessoais deve seguir políticas internas e LGPD (armazenamento transitório, mínimo necessário).
- Limite de 3 entradas por requisição (batch) e até 3 execuções paralelas para evitar sobrecarga.
- Validação prévia de CPF/NIS/nomes; entradas inválidas são rejeitadas sem abrir navegador; logs mascaram identificadores.

## Critérios de avaliação (do desafio)
| Categoria | Detalhes esperados |
|-----------|--------------------|
| Funcionalidade | Execução correta do robô em todos os cenários de teste. |
| Código | Legibilidade, modularização, tratamento de erros. |
| Integrações | Uso eficiente da plataforma de workflow e das APIs do Google |
| Segurança | Boas práticas (OAuth 2.0/JWT, variáveis de ambiente). |
| Documentação | README claro, comentários relevantes. |
| Bônus | Parte 2 e/ou diferenciais (notificações, testes, etc.). |

## Cenários de teste (MOST)
| Cenário | Entrada | Saída esperada |
|---------|---------|----------------|
| Sucesso (CPF) | CPF ou NIS válido | JSON com dados coletados e evidência da tela. |
| Erro (CPF) | CPF ou NIS inexistente | JSON com mensagem de erro: "Não foi possível retornar os dados no tempo de resposta solicitado". |
| Sucesso (Nome) | Nome completo | JSON com dados do primeiro registro equivalente encontrado + evidência. |
| Erro (Nome) | Nome inexistente | JSON com mensagem de erro: "Foram encontrados 0 resultados para o termo …". |
| Filtrado | Sobrenome + filtro social | JSON com dados do primeiro registro equivalente encontrado + evidência. |

## Contrato de resposta da API
- **Consulta única com sucesso (`200`)**: retorna objeto raiz com `pessoa`, `beneficios` e `meta`.
- **Consulta única sem resultado de negócio (`200`)**: retorna `status="error"`, `error`, `beneficios=[]` e `meta` com evidência em Base64.
- **Lote (`200`)**: retorna `resultados[]`, cada item com `consulta`, `status` (`ok`, `invalid` ou `error`) e `resultado`/`error`.
- **Erros de protocolo/autenticação**:
  - `400`: payload inválido, entrada inválida ou limite excedido.
  - `401`: token ausente, inválido ou expirado.
  - `403`: escopo insuficiente.
  - `500`: falha inesperada no processamento.

## Decisões de implementação deste projeto
- Autenticação adotada: Bearer token JWT HS256 com `API_MASTER_KEY` dedicada.
- Configuração por variáveis de ambiente (`DJANGO_SECRET_KEY`, `API_MASTER_KEY`, `ALLOWED_HOSTS`, `API_TOKEN_TTL`, `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OAUTH_AUDIENCE`).
- Batch com até 3 entradas por requisição; paralelismo operacional configurável por ambiente (conservador em produção para estabilidade).
