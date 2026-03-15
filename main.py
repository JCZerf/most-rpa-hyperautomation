import json
import logging
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from bot.scraper import TransparencyBot

MAX_ALVOS = 3
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"execucao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
    force=True,
)
logger = logging.getLogger(__name__)


def _anexar_tempo_execucao(resultado, duracao_ms):
    if not isinstance(resultado, dict):
        return {"resultado": resultado, "duracao_execucao_ms": duracao_ms}
    meta = dict(resultado.get("meta") or {})
    meta["duracao_execucao_ms"] = duracao_ms
    resultado["meta"] = meta
    resultado["duracao_execucao_ms"] = duracao_ms
    return resultado


def executar_para_alvo(identificador_alvo, headless=True, usar_refine=False):
    """Função que será executada em paralelo para cada CPF/Nome."""
    logger.info(f"Iniciando thread para o alvo: {identificador_alvo}")
    inicio = time.perf_counter()
    
    # Instancia o bot em modo headless conforme o desafio pede
    bot = TransparencyBot(headless=headless, alvo=identificador_alvo, usar_refine=usar_refine)
    
    try:
        resultado = bot.run()
        duracao_ms = int((time.perf_counter() - inicio) * 1000)
        resultado = _anexar_tempo_execucao(resultado, duracao_ms)
        if resultado.get("status") == "invalid":
            logger.error(
                f"Entrada inválida para {identificador_alvo}: {resultado.get('error')} "
                f"(duracao={duracao_ms}ms)"
            )
            return resultado
        
        # Salva o resultado individualmente
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Nome do arquivo inclui o alvo para facilitar identificação
        nome_limpo = str(identificador_alvo).replace(".", "").replace("-", "")
        out_file = out_dir / f"result_{nome_limpo}_{timestamp}.json"
        
        with out_file.open("w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=4)
            
        logger.info(f"Sucesso: {identificador_alvo} -> {out_file.name} (duracao={duracao_ms}ms)")
        return resultado

    except Exception as e:
        logger.error(f"Falha crítica no alvo {identificador_alvo}: {e}")
        return {"alvo": identificador_alvo, "error": str(e)}

def main():
    logger.info("--- Iniciando Hyperautomation Most RPA ---")
    logger.info(f"Log da execução salvo em: {LOG_FILE}")
    inicio_total = time.perf_counter()

    # ===== CONFIGURAÇÃO RÁPIDA DE TESTE (EDITE AQUI) =====
    TEST_CONFIG = {
        # "um" = executa só um alvo | "grupo" = executa lista de alvos
        "modo_execucao": "um",
        "alvo_unico": "04031769644",
        "grupo_alvos": [
            "04031769644",
            "A ANNE CHRISTINE SILVA RIBEIRO",
            "A LIDA PEREIRA FIALHO",
        ],
        "headless": False,       # True = sem abrir janela | False = visual
        "refinar_busca": False,  # True = usa filtro beneficiário | False = busca simples
        "max_workers": 3,        # máximo de threads no modo grupo
    }
    # ================================================

    modo_execucao = TEST_CONFIG["modo_execucao"]
    if modo_execucao not in {"um", "grupo"}:
        raise ValueError("modo_execucao inválido. Use 'um' ou 'grupo'.")

    if modo_execucao == "um":
        lista_alvos = [TEST_CONFIG["alvo_unico"]]
    else:
        lista_alvos = TEST_CONFIG["grupo_alvos"]

    if len(lista_alvos) > MAX_ALVOS:
        raise ValueError(f"Máximo permitido: {MAX_ALVOS} alvos por execução local")

    max_workers = min(int(TEST_CONFIG["max_workers"]), len(lista_alvos))
    logger.info(
        "Configuração de teste: modo=%s headless=%s refinar_busca=%s max_workers=%s",
        modo_execucao,
        TEST_CONFIG["headless"],
        TEST_CONFIG["refinar_busca"],
        max_workers,
    )

    # max_workers define quantos navegadores abrirão AO MESMO TEMPO
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(
            executor.map(
                lambda alvo: executar_para_alvo(
                    alvo,
                    headless=TEST_CONFIG["headless"],
                    usar_refine=TEST_CONFIG["refinar_busca"],
                ),
                lista_alvos,
            )
        )

    duracao_total_ms = int((time.perf_counter() - inicio_total) * 1000)
    logger.info(f"--- Todas as execuções foram finalizadas --- (tempo_total_execucao_ms={duracao_total_ms})")

if __name__ == "__main__":
    main()
