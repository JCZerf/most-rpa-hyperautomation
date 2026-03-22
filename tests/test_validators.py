import pytest

from bot.validators import classificar_consulta


@pytest.mark.parametrize(
    "valor, esperado_tipo",
    [
        ("52998224725", "cpf"),   # CPF válido
        ("529.982.247-25", "cpf"),  # CPF válido formatado
        ("00000000000", None),    # inválido
    ],
)
def test_classificar_cpf(valor, esperado_tipo):
    ok, tipo, _, _ = classificar_consulta(valor)
    if esperado_tipo:
        assert ok and tipo == esperado_tipo
    else:
        assert not ok


@pytest.mark.parametrize(
    "valor, valido",
    [
        ("A LIDA PEREIRA FIALHO", True),
        ("A ANNE CHRISTINE SILVA RIBEIRO", True),
        ("", False),
        ("123ABC", False),
    ],
)
def test_classificar_nome(valor, valido):
    ok, tipo, _, _ = classificar_consulta(valor)
    assert ok == valido
    if valido:
        assert tipo == "nome"


def test_classificar_nis_valido():
    # Apenas garante que número com 11 dígitos não quebra e retorna algo coerente
    nis = "12345678909"
    ok, tipo, _, _ = classificar_consulta(nis)
    assert isinstance(ok, bool)


def test_classificar_cpf_formatado_retorna_normalizado():
    ok, tipo, normalizado, _ = classificar_consulta("529.982.247-25")
    assert ok is True
    assert tipo == "cpf"
    assert normalizado == "52998224725"
