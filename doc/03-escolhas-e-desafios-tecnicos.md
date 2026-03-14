## Escolhas técnicas (com opções e justificativa)

- **Backend**  
  - Opções: Django/DRF vs FastAPI.  
  - Escolha: **Django/DRF** porque já havia código e testes prontos, integra fácil com middleware/logs existentes e reduz esforço de migração; custo de performance aceitável para workloads bound em Playwright, não em CPU web.

- **Automation engine**  
  - Opções: Playwright (Chromium headless) vs Selenium.  
  - Escolha: **Playwright** pela API moderna, isolamento de contexto mais simples e download de navegador gerenciado, que diminui flakiness. Mantido Chromium headless para suportar o portal alvo.

- **Execução em nuvem**  
  - Opções: Cloud Run vs Compute Engine/VM dedicada.  
  - Escolha: **Cloud Run** pelo autoscaling gerenciado, faturamento por uso e fácil integração com Artifact Registry e WIF. VM implicaria gerenciar SO e patches, contrariando o prazo/escopo.

- **Autenticação**  
  - Opções: Reutilizar `SECRET_KEY` ou chave dedicada para JWT; HS256 vs RS256.  
  - Escolha: **HS256 com `API_MASTER_KEY` dedicada (>=32 chars)** para separar segredos e simplificar emissão/validação sem depender de pares de chave. Mantido fluxo client_credentials mínimo para o desafio.

- **Deploy/CI**  
  - Opções: Cloud Build trigger vs GitHub Actions com WIF.  
  - Escolha: **GitHub Actions + WIF** porque o repositório já usa GH, reduz chaves estáticas e mantém pipeline único de build/push/deploy.

- **Configuração/vars**  
  - Opções: Passar envs inline no deploy ou via Secret Manager.  
  - Escolha: **Inline + GitHub Secrets** por velocidade; anotado upgrade futuro para Secret Manager se houver tempo/compliance.

- **Escala e recursos**  
  - Opções: Aumentar concorrência ou instâncias com mais memória.  
  - Escolha: **concurrency=1 e instância com 4 Gi / 2 vCPU** para priorizar estabilidade do Chromium durante scraping; preferir right-sizing posterior com métricas (latência, memória e taxa de erro) após validar funcionamento fim a fim.

- **Arquitetura da solução**  
  - Opções: fluxo concentrado em um único arquivo vs separação por responsabilidades.  
  - Escolha: **arquitetura simples e modular**, separando bot e API em arquivos com responsabilidades específicas (`navigation`, `extraction`, `browser`, `views`, `auth`), para facilitar manutenção, testes e evolução incremental.

- **Estratégia de navegação no portal**  
  - Opções: ir direto para a URL interna de pesquisa vs reproduzir o caminho completo do desafio.  
  - Escolha: **seguir o passo a passo solicitado no desafio** (entrada no portal e navegação até a área de consulta), mesmo existindo opção de pular direto para a tela de pesquisa.

- **Estratégia para buscas por nome**  
  - Opções: processar qualquer nome retornando grandes listas vs restringir casos ambíguos.  
  - Escolha: **desconsiderar nomes com resultado excessivo/ambíguo** (ex.: centenas de ocorrências) para reduzir consumo de recurso e evitar extrações incorretas por homônimos.

- **Escopo de extração dos benefícios**  
  - Opções: navegar todas as abas/telas de detalhe vs focar no recorte exigido no desafio.  
  - Escolha: **focar no escopo principal pedido**, extraindo benefícios exigidos com evidências por tela, sem implementar navegação completa por todas as abas secundárias.

## Desafios encontrados
- **Card rotativo na home do Portal da Transparência**: o card de “Pessoas Físicas e Jurídicas” rotaciona automaticamente e, sem tratamento, o bot podia ficar preso rolando/tentando interagir. Mitigação: clique com `force=True` para estabilizar a transição para a etapa seguinte.
- **Resultados amplos em consultas por nome**: algumas entradas retornam 900+ registros, com alto custo computacional e baixa confiabilidade para identificar a pessoa correta. Mitigação: aplicar regra de desambiguação e tratar retornos ambíguos como não elegíveis para extração automática.
- **Evidências e ausência de benefício**: além dos casos positivos, foi necessário tratar explicitamente ausência de benefício com evidência em Base64 para rastreabilidade da execução.
- **OOM no Cloud Run**: Chromium estourou 512 MiB em configurações menores; mitigado com instância mais robusta, `concurrency=1` e ajustes de timeout.
- **Env parsing**: `ALLOWED_HOSTS` quebrava no action; resolvido escapando vírgulas no `env_vars`.
- **Chave JWT curta**: Warnings do PyJWT; exigimos `API_MASTER_KEY` >=32 chars e documentamos no README.
- **Autorização pública**: 403 inicial; corrigido com `allow-unauthenticated` e binding `allUsers`.

## Decisões de escopo para o desafio
- O fluxo foi implementado para atender o caminho de navegação esperado no enunciado, priorizando aderência ao desafio sobre otimizações agressivas de atalho de rota.
- A navegação completa em todas as abas de detalhe não foi implementada nesta versão por decisão consciente de escopo, direcionando esforço para robustez da API, autenticação, evidências e estabilidade de execução.
