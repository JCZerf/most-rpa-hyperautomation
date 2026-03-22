## Formato das respostas da API

Este documento consolida o contrato de saída da API para consultas unitárias e em lote.

#### 1) Consulta única com sucesso (`200 OK`)
```json
{
  "id_consulta": "6a7e35d0-6d19-4e53-8b02-17bb30a8b7f6",
  "data_hora_consulta": "14/03/2026 - 10:30",
  "pessoa": {
    "consulta": "04031769644",
    "nome": "NOME DA PESSOA",
    "cpf": "***.***.***-**",
    "localidade": "UF",
    "quantidade_beneficios": 1,
    "total_recursos_favorecidos": "R$ 600,00"
  },
  "beneficios": [
    {
      "tipo": "Auxílio Brasil",
      "nis": "1234 5678 901",
      "valor_recebido": "R$ 600,00",
      "detalhe_href": "/...",
      "detalhe_evidencia": "<base64>",
      "parcelas": [
        {
          "mes_folha": "01/2024",
          "mes_referencia": "01/2024",
          "uf": "SP",
          "municipio": "São Paulo",
          "quantidade_dependentes": "0",
          "valor": "R$ 600,00"
        }
      ]
    }
  ],
  "meta": {
    "id_consulta": "6a7e35d0-6d19-4e53-8b02-17bb30a8b7f6",
    "data_hora_consulta": "14/03/2026 - 10:30",
    "resultados_encontrados": 1,
    "beneficios_encontrados": [
      "Auxílio Brasil"
    ],
    "panorama_relacao": "<base64>",
    "total_valor_recebido": 600.0,
    "total_valor_recebido_formatado": "R$ 600,00"
  }
}
```

#### 2) Consulta única sem resultado (`200 OK` com `status="not_found"`)
```json
{
  "id_consulta": "67df0b30-d289-4f91-9ff3-1577ec67b4b3",
  "data_hora_consulta": "14/03/2026 - 10:31",
  "status": "not_found",
  "pessoa": {
    "consulta": "04031769644",
    "nome": "N/A",
    "cpf": "N/A",
    "localidade": "N/A",
    "total_recursos_favorecidos": "R$ 0,00"
  },
  "beneficios": [],
  "meta": {
    "id_consulta": "67df0b30-d289-4f91-9ff3-1577ec67b4b3",
    "data_hora_consulta": "14/03/2026 - 10:31",
    "resultados_encontrados": 0,
    "evidencia_resultados_zero": "<base64>",
    "mensagem": "Não foi possível retornar os dados no tempo de resposta solicitado",
    "total_valor_recebido": 0.0,
    "total_valor_recebido_formatado": "R$ 0,00"
  }
}
```

#### 3) Lote (`200 OK`, `207` ou `502` conforme os itens)
```json
{
  "resultados": [
    {
      "consulta": "04031769644",
      "status": "ok",
      "resultado": {
        "id_consulta": "6a7e35d0-6d19-4e53-8b02-17bb30a8b7f6",
        "data_hora_consulta": "14/03/2026 - 10:30",
        "pessoa": {
          "consulta": "04031769644",
          "nome": "NOME DA PESSOA",
          "cpf": "***.***.***-**",
          "localidade": "UF"
        },
        "beneficios": [],
        "meta": {
          "id_consulta": "6a7e35d0-6d19-4e53-8b02-17bb30a8b7f6",
          "data_hora_consulta": "14/03/2026 - 10:30"
        }
      }
    },
    {
      "consulta": "123ABC",
      "status": "invalid",
      "resultado": {
        "status": "invalid",
        "error": "Entrada inválida: use CPF/NIS com 11 dígitos ou nome válido.",
        "id_consulta": "cbef5981-1c2a-4a9b-a6f4-5a5347dff67d",
        "data_hora_consulta": "14/03/2026 - 10:32",
        "pessoa": {
          "consulta": "123ABC",
          "nome": "N/A",
          "cpf": "N/A",
          "localidade": "N/A"
        },
        "meta": {
          "id_consulta": "cbef5981-1c2a-4a9b-a6f4-5a5347dff67d",
          "data_hora_consulta": "14/03/2026 - 10:32"
        }
      }
    }
  ]
}
```

#### 4) Erros de protocolo/segurança

| HTTP | Quando acontece | Exemplo |
|------|------------------|---------|
| `400` | payload inválido, lista vazia, entrada inválida no single | `{"status":"error","error":"Lista \"consultas\" vazia"}` |
| `401` | sem token, token inválido/expirado ou token reutilizado | `{"status":"error","error":"Invalid or expired token"}` |
| `403` | token sem escopo `bot:read` | `{"status":"error","error":"Insufficient scope"}` |
| `207` | lote com sucesso parcial (mistura de itens ok e erro/invalid) | `{"resultados":[{"status":"ok"},{"status":"error"}]}` |
| `500` | falha inesperada no processamento da API | `{"status":"error","error":"<mensagem-interna>"}` |
| `502` | falha do bot/dependência externa durante a consulta | `{"status":"error","error":"<mensagem-do-bot>"}` |
