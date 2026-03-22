## Atalhos rápidos
- Variáveis de ambiente (referência completa): [README - Referência de variáveis de ambiente](../README.md#env-reference)
- Requisitos e contrato da API: [doc/02-requisito-do-projeto.md](./02-requisito-do-projeto.md)

## Escolhas confirmadas da implementação atual
- **Backend e API:** Django/DRF com arquitetura modular atualizada por responsabilidades: `api/views.py` (contrato HTTP e roteamento dos modos single/lote), `api/auth.py` (OAuth2 client_credentials + JWT de uso único), `api/metrics.py` (métricas Prometheus), `bot/scraper.py` (fluxo assíncrono ponta a ponta), `bot/orchestrator.py` (concorrência `1 x N` por abas e fila interna), `bot/navigation.py` + `bot/extraction.py` (navegação e parsing), `bot/browser.py` (contexto Playwright) e `bot/validators.py` (validação/normalização de CPF, NIS e nome).
- **Automação:** Playwright com Chromium em modo headless, mantendo estabilidade operacional para o portal alvo.
- **Desambiguação por nome com score:** a seleção do resultado usa normalização de nome (acentos/pontuação/artigos), cálculo de score de proximidade e escolha do melhor candidato; fallback para o primeiro resultado quando não há índice válido.
- **Escopo de benefícios e layouts:** mapeamento focado nos benefícios exigidos no desafio (Auxílio Brasil, Auxílio Emergencial e Bolsa Família). Para cenários fora do recorte, mantém extração de panorama/dados base sem aprofundar extração não essencial.
- **Escopo de parcelas em detalhe:** a extração atual trabalha com a tabela detalhada visível/compatível na página de detalhe, sem navegação ampla por abas internas adicionais, como estratégia de desempenho e simplicidade para o escopo.
- **Autenticação da API:** OAuth2 client_credentials com JWT HS256 de uso único por consulta (cada chamada exige novo token), chave dedicada (`API_MASTER_KEY`) e expiração de segurança para token não utilizado (`API_TOKEN_TTL`).
  - Observação de implementação atual: o controle de reuso do token é em memória por processo; para unicidade global em múltiplos workers/instâncias, o passo seguinte é store compartilhado.
- **Parâmetro de refinamento:** padronização para `refinar_busca` como campo oficial e único da API.
- **Migração de motor de execução (sync -> async):** a aplicação passou a operar exclusivamente com o bot assíncrono, sem fallback para o modo síncrono.
- **Modelo de concorrência do bot async:** padrão operacional de `1` browser fixo com até `4` consultas simultâneas por abas (configurável por `BOT_MAX_CONSULTAS_POR_BROWSER`).
- **Benchmark de concorrencia (22/03/2026):** comparação `4/2` e `8/1` mostrou que aumentar browsers reduz um pouco o tempo, mas pressiona RAM e degrada estabilidade; na rodada reduzida (`4/1` e `2/2`), ambos estabilizaram, com decisão final de manter browser fixo em `1` e ajustar somente abas.
- **Fila interna de consultas:** quando o lote excede a capacidade paralela (`1 x 4` por padrão), os blocos excedentes entram em fila e são processados assim que houver slot livre, evitando rejeição apenas por volume.
- **Resposta com/sem Base64:** inclusão de `incluir_base64` na API para permitir payload leve (sem evidências/imagens) quando o consumidor não precisa dos anexos.
- **Infraestrutura em nuvem:** escolha por Google Cloud Run pela velocidade de entrega, facilidade operacional e créditos gratuitos no contexto do projeto.
- **Recursos de execução:** perfis leves (ex.: 512MB/1CPU) não suportaram o navegador de forma estável; operação validada entre 2GB e 4GB de RAM com 2 vCPU nos testes.
- **Hiperautomação (bônus):** fluxo funcional no Make, com gravação de JSON no Drive e registro estruturado no Sheets, priorizando entrega do fluxo ponta a ponta.
- **Observabilidade (Prometheus + Grafana + Telegram):** adoção de métricas com Prometheus para séries temporais operacionais da API e visualização/alertas no Grafana.
  - **Motivo do Telegram:** integração nativa e simples para criação de bot/canal de alerta, permitindo receber notificações em poucos minutos com baixa fricção operacional.
  - **Motivo do Prometheus:** modelo robusto para coleta de métricas temporais (latência, volume, status e comportamento do endpoint), facilitando análise histórica e definição de alertas.

## Desafios encontrados e mitigação aplicada
- **Card rotativo na home do portal:** dificultava o clique determinístico no fluxo inicial. Mitigação aplicada com clique forçado e sequência de navegação estabilizada.
- **Sincronização de carregamento nas telas de detalhe:** sem espera adequada, a extração de parcelas podia quebrar. Mitigação com esperas explícitas de carregamento/estado antes de ler tabelas.
- **Intermitência no modo refinado (`refinar_busca=true`):** o container de busca refinada podia permanecer oculto em alguns cenários. Mitigação com fallback de clique forçado e marcação do filtro via JavaScript.
- **Busca simples por nome (`refinar_busca=false`) com timeout em `networkidle`:** a espera por `wait_for_load_state("networkidle")` podia ficar pendente e estourar timeout em consultas por nome.
  - Sintoma: falha intermitente na etapa de carregamento mesmo com resultados já disponíveis no contador.
  - Mitigação aplicada: tolerar timeout de `networkidle`, seguir com sincronização pelo `#countResultados` e validar seleção pelo nome mais próximo.
- **CAPTCHA/WAF e bloqueios progressivos:** houve ocorrência de bloqueio tanto na API em nuvem quanto em máquina local após volume de consultas.
  - Hipótese técnica principal: combinação de telemetria comportamental, assinatura de automação e mecanismos anti-bot do portal.
  - Evidência empírica da fase de testes: cerca de 500 solicitações ao longo de aproximadamente 8 horas antes de bloqueio geral.
  - Situação atual: mitigado parcialmente com tuning de browser/contexto, porém o tratamento definitivo de bloqueio permanece como frente de evolução.
- **Limitação de infraestrutura gratuita:** ambiente com 512MB/1CPU não sustentou execução estável do Playwright; decisão operacional foi usar perfil superior no Google Cloud.
- **Sobrecarga do modelo síncrono legado:** o padrão antigo (1 consulta por browser, até 3 simultâneas) aumentava consumo de CPU/RAM e limitava escalabilidade de raspagem.
  - Mitigação aplicada: adoção de multiplexação assíncrona por abas no mesmo browser/contexto, reduzindo custo por consulta e aumentando throughput.
- **Sobrecarga de RAM com multi-browser no async:** nos benchmarks de 22/03/2026, cenários com mais de um browser simultâneo elevaram consumo de memória/processos e pioraram estabilidade em parte das rodadas.
  - Mitigação aplicada: padronizar browser fixo em `1` e manter ajuste apenas de abas simultâneas (`BOT_MAX_CONSULTAS_POR_BROWSER`), com fila para excedentes.
- **Integrações Make/Drive/Sheets:** implementação inicial foi direta e funcional, porém sem camada completa de regras de negócio por cenário (quando salvar, quando não salvar, validações por ramificação).

## Evoluções possíveis (fora do escopo atual)
- **Controle global de token com Redis:** mover o controle de reuso de JWT (`jti`) de memória local para store compartilhado, garantindo unicidade entre múltiplos workers/instâncias.
- **Navegação por abas adicionais de parcelas:** expandir extração para percorrer abas internas de detalhe quando existirem, cobrindo mais layouts de forma automática.
- **Expansão de layouts não prioritários:** adicionar parsing dedicado para benefícios/telas não exigidos no recorte original.
- **Política avançada de persistência no Make:** regras condicionais de gravação em Drive/Sheets, tratamento por tipo de retorno e governança de expurgo/retensão.
- **Camada anti-bloqueio/WAF mais robusta:** estratégias adicionais de redução de assinatura de automação, controle de ritmo e observabilidade específica de bloqueios.

## Referências de evidência
- Consolidado de status/evidências gerais: [doc/04-status-do-projeto.md](./04-status-do-projeto.md)
- E2E smoke pós-deploy (run `23096919987`) - artefatos: [e2e-smoke-artifacts](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-23096919987/e2e-smoke-artifacts)
- E2E smoke pós-deploy - metadados: [README](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-23096919987/README.md)
- E2E smoke concorrente local - artefatos: [e2e-smoke-artifacts](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-local-concorrencia/e2e-smoke-artifacts)
- E2E smoke concorrente local - metadados: [README](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-local-concorrencia/README.md)
- E2E smoke manual sucesso - artefatos: [e2e-smoke-artifacts](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-manual-successo/e2e-smoke-artifacts)
- E2E smoke manual sucesso - metadados: [README](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/e2e-smoke/2026-03-14-run-manual-successo/README.md)
- Evidência de documentação da API (Swagger + auth): [README](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/api-docs/2026-03-14-19h/README.md)
- Evidência visual da documentação API: [tela_doc_api.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/api-docs/2026-03-14-19h/tela_doc_api.png)
- Evidência visual de geração de token/JWT: [auth_geracao_jwt.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/api-docs/2026-03-14-19h/auth_geracao_jwt.png)
- Evidências de performance em HML: [observacoes.md](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/performance-hml/2026-03-14-19h/observacoes.md)
- Evidência visual de performance (busca única): [busca_unica_refine_false.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/performance-hml/2026-03-14-19h/busca_unica_refine_false.png)
- Evidência visual de performance (lote avançado): [busca_em_lote_avançado.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/performance-hml/2026-03-14-19h/busca_em_lote_avançado.png)
- Evidência visual de performance (lote simples + refine): [Lote_simples+refine_true.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/doc/evidencias/performance-hml/2026-03-14-19h/Lote_simples+refine_true.png)
- Evidência de integração com Google Sheets (v1): [google_sheets_evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_sheets_evidencia.png)
- Evidência de integração com Google Sheets (v2): [google_sheets_evidencia_V2.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_sheets_evidencia_V2.png)
- Evidência de integração com Google Drive: [google_driver_evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_driver_evidencia.png)
- Evidência do fluxo Make (módulos): [make_evidencia_workflow.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/make_evidencia_workflow.png)
- Evidência do fluxo Make (visão geral): [workflow.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/workflow.png)
- Evidência de observabilidade (dashboard Grafana): [grafana_basic_painel.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/grafana_basic_painel.png)
- Evidência de observabilidade (alerta Telegram): [telegram-notification-evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/telegram-notification-evidencia.png)
- Demo de execução async: [demonstração_async.mp4](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/demonstração_async.mp4)
