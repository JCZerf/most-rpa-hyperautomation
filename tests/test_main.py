import types

import bot.main as main


def test_remover_imagens_base64_remove_chaves_de_evidencia():
    payload = {
        "id_consulta": "x",
        "meta": {
            "panorama_relacao": "BASE64",
            "ok": True,
        },
        "beneficios": [
            {"detalhe_evidencia": "BASE64", "tipo": "Auxílio Brasil"},
            {"tipo": "Bolsa Família"},
        ],
    }

    out = main._remover_imagens_base64(payload)
    assert out["id_consulta"] == "x"
    assert out["meta"]["ok"] is True
    assert "panorama_relacao" not in out["meta"]
    assert "detalhe_evidencia" not in out["beneficios"][0]


def test_chunked_divide_lista_em_blocos():
    items = ["a", "b", "c", "d", "e"]
    blocos = list(main._chunked(items, 2))
    assert blocos == [["a", "b"], ["c", "d"], ["e"]]


def test_normalizar_consultas_prioriza_cli():
    args = types.SimpleNamespace(consultas=[" 04031769644 "], consultas_json=None)
    out = main._normalizar_consultas(args)
    assert out == ["04031769644"]


def test_normalizar_consultas_com_json():
    args = types.SimpleNamespace(consultas=None, consultas_json='["A ANNE CHRISTINE SILVA RIBEIRO"," "]')
    out = main._normalizar_consultas(args)
    assert out == ["A ANNE CHRISTINE SILVA RIBEIRO"]


def test_normalizar_consultas_json_invalido():
    args = types.SimpleNamespace(consultas=None, consultas_json='{"nao":"lista"}')
    try:
        main._normalizar_consultas(args)
        raise AssertionError("Era esperado ValueError")
    except ValueError as exc:
        assert "lista JSON" in str(exc)
