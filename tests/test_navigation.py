from bot.navigation import _nome_corresponde_busca


def test_nome_corresponde_ignora_artigo():
    assert _nome_corresponde_busca(
        "A ANNE CHRISTINE SILVA RIBEIRO",
        "ANNE CHRISTINE SILVA RIBEIRO",
    )


def test_nome_corresponde_ignora_acento():
    assert _nome_corresponde_busca(
        "MARILÚCIA GASPARINI DE OLIVAS",
        "MARILUCIA GASPARINI OLIVAS",
    )


def test_nome_corresponde_rejeita_nome_diferente():
    assert not _nome_corresponde_busca(
        "MARILUCIA GASPARINI DE OLIVAS",
        "JOAO DA SILVA",
    )
