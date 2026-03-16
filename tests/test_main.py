import logging
import types

import main


def test_anexar_tempo_execucao_dict():
    payload = {"meta": {"foo": "bar"}}
    out = main._anexar_tempo_execucao(payload, 1234)
    assert out["duracao_execucao_ms"] == 1234
    assert out["meta"]["duracao_execucao_ms"] == 1234
    assert out["meta"]["foo"] == "bar"


def test_executar_para_alvo_inclui_duracao(monkeypatch, tmp_path):
    class FakeBot:
        def __init__(self, headless, alvo, usar_refine=False):
            self.headless = headless
            self.alvo = alvo
            self.usar_refine = usar_refine

        def run(self):
            return {"pessoa": {"consulta": self.alvo}, "beneficios": [], "meta": {}}

    times = iter([10.0, 12.5])  # 2500ms
    monkeypatch.setattr(main, "TransparencyBot", FakeBot)
    monkeypatch.setattr(main.time, "perf_counter", lambda: next(times))
    monkeypatch.chdir(tmp_path)

    resultado = main.executar_para_alvo("FULANO TESTE")

    assert resultado["duracao_execucao_ms"] == 2500
    assert resultado["meta"]["duracao_execucao_ms"] == 2500
    files = list((tmp_path / "output").glob("result_*.json"))
    assert len(files) == 1


def test_main_loga_tempo_total(monkeypatch, caplog):
    class DummyExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def map(self, fn, items):
            return [fn(i) for i in items]

    times = iter([100.0, 101.2])  # 1200ms
    monkeypatch.setattr(main, "ThreadPoolExecutor", DummyExecutor)
    monkeypatch.setattr(main, "executar_para_alvo", lambda *args, **kwargs: {"status": "ok", "meta": {}})
    monkeypatch.setattr(main.time, "perf_counter", lambda: next(times))

    caplog.set_level(logging.INFO)
    main.main()

    assert "tempo_total_execucao_ms=1200" in caplog.text
