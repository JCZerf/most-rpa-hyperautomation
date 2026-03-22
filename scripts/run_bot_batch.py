#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.orchestrator import env_bool, executar_consultas_em_lote_async, get_runtime_limits


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    return default


def _parse_consultas() -> list[str]:
    consultas_json = (os.getenv("BOT_CONSULTAS_JSON") or "").strip()
    if consultas_json:
        try:
            data = json.loads(consultas_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"BOT_CONSULTAS_JSON invalido: {exc}") from exc
        if not isinstance(data, list):
            raise ValueError("BOT_CONSULTAS_JSON deve ser uma lista JSON.")
        consultas = [str(item).strip() for item in data if str(item).strip()]
    else:
        consulta_unica = (os.getenv("BOT_CONSULTA") or "").strip()
        consultas = [consulta_unica] if consulta_unica else []

    if not consultas:
        raise ValueError("Nenhuma consulta informada. Defina BOT_CONSULTA ou BOT_CONSULTAS_JSON.")
    return consultas


def _slug_consulta(valor: str) -> str:
    clean = "".join(ch if ch.isalnum() else "_" for ch in valor.strip())
    while "__" in clean:
        clean = clean.replace("__", "_")
    clean = clean.strip("_")
    return clean[:60] or "consulta"


def _extract_auditoria(resultado: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if not isinstance(resultado, dict):
        return None, None
    id_consulta = resultado.get("id_consulta")
    data_hora_consulta = resultado.get("data_hora_consulta")
    if not id_consulta or not data_hora_consulta:
        meta = resultado.get("meta")
        if isinstance(meta, dict):
            id_consulta = id_consulta or meta.get("id_consulta")
            data_hora_consulta = data_hora_consulta or meta.get("data_hora_consulta")
    return id_consulta, data_hora_consulta


def main() -> int:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(os.getenv("BOT_OUTPUT_DIR", "output/stress-bot"))
    out_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
        force=True,
    )
    logger = logging.getLogger("bot_batch_runner")

    try:
        consultas = _parse_consultas()
    except ValueError as exc:
        logger.error(str(exc))
        return 2

    headless = _parse_bool(os.getenv("BOT_HEADLESS"), True)
    refinar_busca = _parse_bool(os.getenv("BOT_REFINAR_BUSCA"), False)
    incluir_base64 = _parse_bool(os.getenv("BOT_INCLUIR_BASE64"), False)
    max_browsers, max_consultas_por_browser = get_runtime_limits()

    logger.info(
        "Iniciando batch async: consultas=%s headless=%s refinar_busca=%s incluir_base64=%s max_browsers=%s max_consultas_por_browser=%s",
        len(consultas),
        headless,
        refinar_busca,
        incluir_base64,
        max_browsers,
        max_consultas_por_browser,
    )
    logger.info("Consultas: %s", consultas)

    started_all = time.perf_counter()
    itens_execucao = [
        {"indice_entrada": idx, "consulta": consulta, "refinar_busca": refinar_busca}
        for idx, consulta in enumerate(consultas)
    ]

    saida_execucao = asyncio.run(
        executar_consultas_em_lote_async(
            itens_execucao,
            headless=headless,
            max_consultas_por_browser=max_consultas_por_browser,
            incluir_base64=incluir_base64,
        )
    )

    resultados: list[dict[str, Any] | None] = [None] * len(consultas)
    demarcacao_consultas: list[dict[str, Any] | None] = [None] * len(consultas)
    for item in saida_execucao.get("resultados", []):
        idx = int(item.get("indice_entrada", -1))
        if idx < 0 or idx >= len(consultas):
            continue
        consulta = consultas[idx]
        consulta_ordem = f"consulta_{idx + 1}"
        result = item.get("resultado") or {"status": "error", "error": "resultado ausente"}
        status = result.get("status", "ok")
        logger.info("Consulta finalizada: alvo=%s status=%s", consulta, status)
        id_consulta, data_hora_consulta = _extract_auditoria(result)

        item_payload = {
            "consulta_ordem": consulta_ordem,
            "consulta": consulta,
            "status": status,
            "duracao_segundos": float(item.get("duracao_segundos", 0.0)),
            "resultado": result,
        }
        resultados[idx] = item_payload

        item_file = out_dir / f"item_{idx+1}_{_slug_consulta(consulta)}_{run_id}.json"
        with item_file.open("w", encoding="utf-8") as fp:
            json.dump(item_payload, fp, ensure_ascii=False, indent=2)
        logger.info("Arquivo de resultado por consulta: %s", item_file)
        demarcacao_consultas[idx] = {
            "consulta_ordem": consulta_ordem,
            "indice_resultados": idx,
            "consulta": consulta,
            "status": status,
            "id_consulta": id_consulta,
            "data_hora_consulta": data_hora_consulta,
            "arquivo_resultado_consulta": str(item_file),
        }

    for idx, item in enumerate(resultados):
        if item is not None:
            continue
        consulta = consultas[idx]
        consulta_ordem = f"consulta_{idx + 1}"
        item_payload = {
            "consulta_ordem": consulta_ordem,
            "consulta": consulta,
            "status": "error",
            "error": "resultado ausente",
        }
        resultados[idx] = item_payload
        item_file = out_dir / f"item_{idx+1}_{_slug_consulta(consulta)}_{run_id}.json"
        with item_file.open("w", encoding="utf-8") as fp:
            json.dump(item_payload, fp, ensure_ascii=False, indent=2)
        demarcacao_consultas[idx] = {
            "consulta_ordem": consulta_ordem,
            "indice_resultados": idx,
            "consulta": consulta,
            "status": "error",
            "id_consulta": None,
            "data_hora_consulta": None,
            "arquivo_resultado_consulta": str(item_file),
        }

    total_ms = int((time.perf_counter() - started_all) * 1000)
    payload = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "consultas": consultas,
        "headless": headless,
        "refinar_busca": refinar_busca,
        "incluir_base64": incluir_base64,
        "meta_execucao": saida_execucao.get("meta_execucao", {}),
        "duracao_total_ms": total_ms,
        "demarcacao_consultas": demarcacao_consultas,
        "resultados": resultados,
    }
    output_file = out_dir / f"batch_result_{run_id}.json"
    with output_file.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)

    logger.info("Execucao finalizada em %sms", total_ms)
    logger.info("Arquivo de resultado: %s", output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
