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
  - Escolha: **concurrency=1 e memória 2 Gi** para evitar OOM com Chromium; preferir escala horizontal (mais instâncias) se precisar de throughput.

## Desafios encontrados
- **OOM no Cloud Run**: Chromium estourou 512 MiB; mitigado elevando para 2 Gi e concurrency=1. Necessário revisar cleanup do Playwright para estabilidade.
- **Env parsing**: `ALLOWED_HOSTS` quebrava no action; resolvido escapando vírgulas no `env_vars`.
- **Chave JWT curta**: Warnings do PyJWT; exigimos `API_MASTER_KEY` >=32 chars e documentamos no README.
- **Autorização pública**: 403 inicial; corrigido com `allow-unauthenticated` e binding `allUsers`.
