## Atalhos rápidos
- Variáveis de ambiente (referência completa): [README - Referência de variáveis de ambiente](../README.md#env-reference)
- Requisitos e contrato da API: [doc/02-requisito-do-projeto.md](./02-requisito-do-projeto.md)

## Escolhas confirmadas da implementação atual
- **Backend e API:** Django/DRF com arquitetura modular (`navigation`, `extraction`, `browser`, `views`, `auth`) para separar responsabilidades e simplificar manutenção.
- **Automação:** Playwright com Chromium em modo headless, mantendo estabilidade operacional para o portal alvo.
- **Desambiguação por nome com score:** a seleção do resultado usa normalização de nome (acentos/pontuação/artigos), cálculo de score de proximidade e escolha do melhor candidato; fallback para o primeiro resultado quando não há índice válido.
- **Escopo de benefícios e layouts:** mapeamento focado nos benefícios exigidos no desafio (Auxílio Brasil, Auxílio Emergencial e Bolsa Família). Para cenários fora do recorte, mantém extração de panorama/dados base sem aprofundar extração não essencial.
- **Escopo de parcelas em detalhe:** a extração atual trabalha com a tabela detalhada visível/compatível na página de detalhe, sem navegação ampla por abas internas adicionais, como estratégia de desempenho e simplicidade para o escopo.
- **Autenticação da API:** OAuth2 client_credentials com JWT HS256, chave dedicada (`API_MASTER_KEY`) e TTL padrão de 10 minutos (`API_TOKEN_TTL=600`).
- **Parâmetro de refinamento:** padronização para `refinar_busca` como campo oficial e único da API.
- **Infraestrutura em nuvem:** escolha por Google Cloud Run pela velocidade de entrega, facilidade operacional e créditos gratuitos no contexto do projeto.
- **Recursos de execução:** perfis leves (ex.: 512MB/1CPU) não suportaram o navegador de forma estável; operação validada entre 2GB e 4GB de RAM com 2 vCPU nos testes.
- **Hiperautomação (bônus):** fluxo funcional no Make, com gravação de JSON no Drive e registro estruturado no Sheets, priorizando entrega do fluxo ponta a ponta.

## Desafios encontrados e mitigação aplicada
- **Card rotativo na home do portal:** dificultava o clique determinístico no fluxo inicial. Mitigação aplicada com clique forçado e sequência de navegação estabilizada.
- **Sincronização de carregamento nas telas de detalhe:** sem espera adequada, a extração de parcelas podia quebrar. Mitigação com esperas explícitas de carregamento/estado antes de ler tabelas.
- **Intermitência no modo refinado (`refinar_busca=true`):** o container de busca refinada podia permanecer oculto em alguns cenários. Mitigação com fallback de clique forçado e marcação do filtro via JavaScript.
- **CAPTCHA/WAF e bloqueios progressivos:** houve ocorrência de bloqueio tanto na API em nuvem quanto em máquina local após volume de consultas.
  - Hipótese técnica principal: combinação de telemetria comportamental, assinatura de automação e mecanismos anti-bot do portal.
  - Evidência empírica da fase de testes: cerca de 500 solicitações ao longo de aproximadamente 8 horas antes de bloqueio geral.
  - Situação atual: mitigado parcialmente com tuning de browser/contexto, porém o tratamento definitivo de bloqueio permanece como frente de evolução.
- **Limitação de infraestrutura gratuita:** ambiente com 512MB/1CPU não sustentou execução estável do Playwright; decisão operacional foi usar perfil superior no Google Cloud.
- **Integrações Make/Drive/Sheets:** implementação inicial foi direta e funcional, porém sem camada completa de regras de negócio por cenário (quando salvar, quando não salvar, validações por ramificação).

## Evoluções possíveis (fora do escopo atual)
- **Navegação por abas adicionais de parcelas:** expandir extração para percorrer abas internas de detalhe quando existirem, cobrindo mais layouts de forma automática.
- **Expansão de layouts não prioritários:** adicionar parsing dedicado para benefícios/telas não exigidos no recorte original.
- **Política avançada de persistência no Make:** regras condicionais de gravação em Drive/Sheets, tratamento por tipo de retorno e governança de expurgo/retensão.
- **Camada anti-bloqueio/WAF mais robusta:** estratégias adicionais de redução de assinatura de automação, controle de ritmo e observabilidade específica de bloqueios.
- **Right-sizing contínuo:** ajustar CPU/memória com base em métrica de latência, taxa de sucesso e taxa de erro em produção.

## Referências de evidência
- Evidências E2E smoke e concorrência: [doc/04-status-do-projeto.md](./04-status-do-projeto.md)
- Evidência de integração com Google Sheets: [google_sheets_evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_sheets_evidencia.png)
- Evidência de integração com Google Drive: [google_driver_evidencia.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/google_driver_evidencia.png)
- Evidência do fluxo Make: [make_evidencia_workflow.png](/home/jcarlos/Documents/work-projects/most-rpa-hyperautomation/img/make_evidencia_workflow.png)
