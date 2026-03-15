from bot.extraction import (
    _parse_linha_disponibilizado,
    _parse_linha_generica,
    _parse_linha_valores_recebidos,
    _parse_linha_valores_sacados,
)


def test_parse_linha_valores_recebidos():
    row = ["01/2024", "01/2024", "SP", "São Paulo", "0", "R$ 600,00"]
    parsed = _parse_linha_valores_recebidos(row)
    assert parsed is not None
    assert parsed["mes_folha"] == "01/2024"
    assert parsed["valor"] == "R$ 600,00"


def test_parse_linha_disponibilizado():
    row = ["01/2024", "1", "SP", "São Paulo", "Elegível", "R$ 600,00", "Sem obs."]
    parsed = _parse_linha_disponibilizado(row)
    assert parsed is not None
    assert parsed["parcela"] == "1"
    assert parsed["enquadramento"] == "Elegível"


def test_parse_linha_valores_sacados():
    row = ["01/2024", "01/2024", "SP", "São Paulo", "R$ 300,00"]
    parsed = _parse_linha_valores_sacados(row)
    assert parsed is not None
    assert parsed["mes_referencia"] == "01/2024"
    assert parsed["valor_parcela"] == "R$ 300,00"


def test_parse_linha_generica():
    row = ["A", "B", "C"]
    parsed = _parse_linha_generica(row)
    assert parsed == {"col_0": "A", "col_1": "B", "col_2": "C"}


def test_parse_linhas_insuficientes_retorna_none():
    assert _parse_linha_valores_recebidos(["a"]) is None
    assert _parse_linha_disponibilizado(["a"]) is None
    assert _parse_linha_valores_sacados(["a"]) is None
