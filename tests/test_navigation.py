from bot.navigation import _escolher_indice_nome_mais_proximo, _score_nome_proximidade


def test_score_nome_proximidade_exato():
    score = _score_nome_proximidade("MARIA DA SILVA", "Maria da Silva")
    assert score == 100


def test_score_nome_proximidade_parcial_relevante():
    score = _score_nome_proximidade("A ANNE CHRISTINE SILVA RIBEIRO", "ANNE CHRISTINE S RIBEIRO")
    assert score >= 60


def test_escolher_indice_nome_mais_proximo():
    nomes = [
        "JOAO PEREIRA",
        "ANNE CHRISTINE SILVA RIBEIRO",
        "MARIA JOSE",
    ]
    idx, score = _escolher_indice_nome_mais_proximo("A ANNE CHRISTINE SILVA RIBEIRO", nomes)
    assert idx == 1
    assert score >= 90
