import pytest

from tests.e2e.test_e2e_smoke import _assert_consulta_contract


def _batch_ok_result(consulta: str) -> dict:
    return {
        "status": "ok",
        "pessoa": {"consulta": consulta, "nome": "Teste", "cpf": "***.***.***-**", "localidade": "UF"},
        "beneficios": [],
        "meta": {"id_consulta": "123", "data_hora_consulta": "24/03/2026 - 21:17"},
    }


@pytest.mark.parametrize(
    ("status_code", "body"),
    [
        (
            200,
            {
                "resultados": [
                    {"consulta": "A", "status": "ok", "resultado": _batch_ok_result("A")},
                    {"consulta": "B", "status": "not_found", "resultado": {**_batch_ok_result("B"), "status": "not_found"}},
                ],
                "meta_execucao": {"total_consultas": 2},
            },
        ),
        (
            207,
            {
                "resultados": [
                    {"consulta": "A", "status": "ok", "resultado": _batch_ok_result("A")},
                    {
                        "consulta": "B",
                        "status": "error",
                        "resultado": {"status": "error", "error": "falha externa"},
                    },
                ],
                "meta_execucao": {"total_consultas": 2},
            },
        ),
        (
            400,
            {
                "resultados": [
                    {
                        "consulta": "123ABC",
                        "status": "invalid",
                        "resultado": {
                            "status": "invalid",
                            "error": "Entrada invalida",
                            "pessoa": {"consulta": "123ABC", "nome": "N/A", "cpf": "N/A", "localidade": "N/A"},
                            "beneficios": [],
                            "meta": {"id_consulta": "456", "data_hora_consulta": "24/03/2026 - 21:17"},
                        },
                    }
                ],
                "meta_execucao": {"total_consultas": 1},
            },
        ),
        (
            502,
            {
                "resultados": [
                    {
                        "consulta": "A",
                        "status": "error",
                        "resultado": {"status": "error", "error": "falha externa"},
                    },
                    {
                        "consulta": "B",
                        "status": "error",
                        "error": "Resultado ausente",
                    },
                ],
                "meta_execucao": {"total_consultas": 2},
            },
        ),
    ],
)
def test_assert_consulta_contract_accepts_batch_envelopes(status_code: int, body: dict):
    _assert_consulta_contract(status_code, body)
