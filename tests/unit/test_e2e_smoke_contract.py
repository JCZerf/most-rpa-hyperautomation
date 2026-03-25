import pytest

from tests.e2e.test_e2e_smoke import (
    _assert_consulta_contract,
    _summarize_batch_statuses,
    _summarize_parallel_batch_results,
)


def _batch_ok_result(consulta: str) -> dict:
    return {
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


def test_summarize_batch_statuses_counts_success_and_errors():
    resumo = _summarize_batch_statuses(
        {
            "resultados": [
                {"consulta": "A", "status": "ok", "resultado": _batch_ok_result("A")},
                {"consulta": "B", "status": "not_found", "resultado": {**_batch_ok_result("B"), "status": "not_found"}},
                {"consulta": "C", "status": "error", "resultado": {"status": "error", "error": "falha"}},
            ]
        }
    )

    assert resumo["total"] == 3
    assert resumo["success_count"] == 2
    assert resumo["counts"]["error"] == 1
    assert resumo["success_rate"] == pytest.approx(2 / 3)


def test_summarize_parallel_batch_results_aggregates_multiple_responses():
    resumo = _summarize_parallel_batch_results(
        [
            (
                207,
                {
                    "resultados": [
                        {"consulta": "A", "status": "ok", "resultado": _batch_ok_result("A")},
                        {"consulta": "B", "status": "error", "resultado": {"status": "error", "error": "falha"}},
                    ]
                },
            ),
            (
                200,
                {
                    "resultados": [
                        {"consulta": "C", "status": "ok", "resultado": _batch_ok_result("C")},
                        {"consulta": "D", "status": "ok", "resultado": _batch_ok_result("D")},
                    ]
                },
            ),
        ]
    )

    assert resumo["total_items"] == 4
    assert resumo["success_count"] == 3
    assert resumo["counts"]["error"] == 1
    assert resumo["response_codes"] == {"207": 1, "200": 1}
    assert resumo["success_rate"] == pytest.approx(0.75)
