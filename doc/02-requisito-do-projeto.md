## Requisitos técnicos
- Backend em Python usando Django para disponibilizar o robô como API (recebe parâmetros e retorna JSON).
- Automação de navegação com Playwright (Chrome/Chromium headless).
- Geração de evidência (screenshot) convertida para Base64 e embutida na resposta.
- Estrutura de resposta em JSON contendo panorama, detalhes de benefícios e imagem.
- Logs de execução e falhas registrados pelo serviço Django.

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
