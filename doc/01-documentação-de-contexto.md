## Atalhos rápidos
- Variáveis de ambiente (referência completa): [README - Referência de variáveis de ambiente](../README.md#env-reference)
- Requisitos e contrato da API: [doc/02-requisito-do-projeto.md](./02-requisito-do-projeto.md)

## Visão geral
- **Aplicação:** Robô de Automação Robótica de Processos (RPA) com abordagem de hiperautomação em Python.
- **Propósito:** Automatizar a coleta de dados do Portal da Transparência (consulta “Pessoas Físicas e Jurídicas”) e entregar um JSON consolidado com evidência em Base64 para uso em fluxos internos.

## Contexto do desafio
- **Parte 1 (obrigatória):** automação web em Python para navegar no portal, consultar por nome/CPF/NIS, extrair dados, gerar evidência e retornar JSON.
- **Parte 2 (bônus):** orquestração via workflow low-code/no-code para acionar API do robô, salvar JSON no Google Drive e atualizar Google Sheets.
- **Entrega esperada:** código-fonte, documentação técnica (decisões e desafios) e demonstração prática com execução simultânea.

## Problema e oportunidade
- Consultas manuais no Portal da Transparência são repetitivas, suscetíveis a erros e lentas.
- Necessidade de padronizar evidências e consolidar benefícios de programas sociais em um formato consumível por outros sistemas.

## Público-alvo e stakeholders
- **Usuários de negócio:** times de compliance, auditoria e análise de benefícios.
- **Equipe técnica:** desenvolvedores Python/RPA e operadores de automação.
- **Governança/segurança:** responsáveis por LGPD e controle de acesso aos insumos (CPF/NIS).

## Escopo
- Navegar no Portal da Transparência até “Pessoas Físicas e Jurídicas”.
- Inserir parâmetros obrigatórios: CPF, nome ou NIS; parâmetro opcional: beneficiário de programa social.
- Coletar dados da tela “Pessoa Física - Panorama da relação da pessoa com o Governo Federal”.
- Capturar imagem da tela e convertê-la para Base64 como evidência.
- Para cada benefício encontrado (Auxílio Brasil, Auxílio Emergencial, Bolsa Família), abrir detalhes e extrair informações.
- Gerar JSON final com dados coletados e a imagem Base64.

## Fora de escopo
- Qualquer edição ou correção de dados no Portal da Transparência.
- Persistência em banco de dados próprio da aplicação (a API retorna JSON por execução e não grava histórico em DB interno).
- Autenticação/logon em áreas restritas do portal (uso apenas de consulta pública).
- Desenvolvimento de conectores proprietários para ERPs/CRMs legados além da automação já entregue via Make + Google Drive + Google Sheets.

## Premissas
- Portal da Transparência permanece acessível publicamente sem autenticação para consultas de pessoas físicas.
- Os parâmetros fornecidos (CPF, nome ou NIS) são válidos e autorizados para uso conforme políticas internas e LGPD.
- Ambiente de execução tem conectividade estável e permite captura de tela.

## Restrições
- Conformidade com LGPD: uso mínimo de dados pessoais, trilha de auditoria das execuções e política de retenção/expurgo para qualquer persistência externa (ex.: Drive/Sheets).
- Dependência de estabilidade e layout do Portal da Transparência; mudanças podem quebrar seletores.
- Tempo de execução deve ser compatível com janelas operacionais do time (definir SLA posteriormente).

## Entradas e saídas
- **Entradas obrigatórias:** CPF, nome ou NIS (ao menos um).
- **Entrada opcional:** beneficiário de programa social.
- **Saída:** JSON contendo dados do panorama, detalhes de benefícios (Auxílio Brasil, Auxílio Emergencial, Bolsa Família) e imagem Base64 da tela.

## Critérios de sucesso (iniciais)
- Execução ponta a ponta sem intervenção manual para casos válidos.
- Evidência de tela capturada e embutida em Base64 no JSON.
- Cobertura explícita e validada dos benefícios: Auxílio Brasil, Auxílio Emergencial e Bolsa Família, quando presentes.
