## 🛠️ Tecnologias e Diferenciais Técnicos

- **Playwright (Python):** Escolhido pela superioridade no tratamento de SPAs e sincronismo nativo de elementos assíncronos, além do isolamento de contextos para execuções paralelas.
- **Execução em Larga Escala:** Suporte a execuções simultâneas via `ThreadPoolExecutor`, permitindo o processamento de múltiplos alvos em instâncias isoladas do Chromium.
- **Hiperautomação de Benefícios:** Lógica iterativa que mapeia e extrai detalhes de múltiplos programas sociais (Auxílio Brasil, Bolsa Família, Auxílio Emergencial) automaticamente.
- **Evidência em Base64:** Capturas de tela convertidas em strings Base64 integradas diretamente no JSON de saída, eliminando a dependência de arquivos de imagem externos.
- **Normalização e Fuzzy Matching:** Algoritmos de limpeza de texto e comparação aproximada (`difflib`) para garantir o clique no alvo correto mesmo com variações de acentuação ou nomes abreviados.

## 🤖 Execução e Paralelismo

O projeto foi configurado para rodar em modo **Headless** por padrão para atender aos requisitos de performance. 

Para rodar múltiplos alvos simultaneamente:
1. Adicione os nomes/CPFs na lista `lista_alvos` dentro do `main.py`.
2. Execute `python main.py`.

## 📂 Estrutura do JSON (Exemplo Real)
O arquivo gerado agora consolida todos os benefícios encontrados para o CPF/Nome:

```json
{
  "pessoa": {
    "nome": "A LIDA PEREIRA FIALHO",
    "cpf": "***.***.***-**",
    "nis": "20111331964"
  },
  "beneficios": [
    {
      "tipo": "Auxílio Brasil",
      "valor_total": "R$ 4.666,00",
      "parcelas": [...],
      "evidencia_detalhe_base64": "/9j/4AAQSkZJRgABAQ..."
    },
    {
      "tipo": "Bolsa Família",
      "valor_total": "R$ 1.442,00",
      "parcelas": [...],
      "evidencia_detalhe_base64": "/9j/4AAQSkZJRgABAQ..."
    }
  ],
  "meta": {
    "data_consulta": "12/03/2026",
    "total_processados": 2
  }
}