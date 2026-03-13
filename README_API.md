# API local mínima

Endpoint disponível após iniciar o Django devserver:

- POST /api/consulta/  
  Body JSON: `{ "consulta": "04031769644", "refine": false }`  
  Retorna: JSON com o resultado do `TransparencyBot`.

Observações:
- A execução é síncrona e bloqueante. Para produção, mova a execução para um worker (Celery/RQ) e retorne um job id.
- Certifique-se de instalar `Django` e dependências (Playwright) no ambiente virtual.

Como rodar (exemplo local):

```bash
python -m pip install django
python manage.py runserver 0.0.0.0:8000
```

Teste com `curl`:

```bash
curl -X POST http://127.0.0.1:8000/api/consulta/ -H "Content-Type: application/json" \
  -d '{"consulta":"04031769644","refine":false}'
```

Swagger UI (se `drf-spectacular` instalado):

 - `http://127.0.0.1:8000/api/docs/` (interface Swagger interativa)

