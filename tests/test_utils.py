from bot.utils import valor_texto_para_float, formatar_brl


def test_valor_texto_para_float_brl():
    assert valor_texto_para_float("R$ 1.234,56") == 1234.56
    assert valor_texto_para_float("R$ 0,00") == 0.0
    assert valor_texto_para_float("") == 0.0


def test_formatar_brl():
    assert formatar_brl(1234.56) == "R$ 1.234,56"
    assert formatar_brl(0.0) == "R$ 0,00"
