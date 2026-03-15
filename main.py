import json
import logging
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from bot.scraper import TransparencyBot

MAX_ALVOS = 3

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_execution.log", encoding="utf-8")
    ]
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

def executar_para_alvo(identificador_alvo):
    """Função que será executada em paralelo para cada CPF/Nome."""
    logger.info(f"Iniciando thread para o alvo: {identificador_alvo}")
    inicio = time.perf_counter()
    
    # Instancia o bot em modo headless conforme o desafio pede
    bot = TransparencyBot(headless=False, alvo=identificador_alvo)
    
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
    inicio_total = time.perf_counter()
    
    # LISTA DE ALVOS PARA EXECUÇÃO SIMULTÂNEA
    lista_alvos = [
        "04031769644",  # Exemplo de NIS CPF
        "A ANNE CHRISTINE SILVA RIBEIRO",  # Exemplo de Nome
        "A LIDA PEREIRA FIALHO"    # Exemplo de Nome
    ]

    if len(lista_alvos) > MAX_ALVOS:
        raise ValueError(f"Máximo permitido: {MAX_ALVOS} alvos por execução local")

    # max_workers define quantos navegadores abrirão AO MESMO TEMPO
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(executar_para_alvo, lista_alvos))

    duracao_total_ms = int((time.perf_counter() - inicio_total) * 1000)
    logger.info(f"--- Todas as execuções foram finalizadas --- (tempo_total_execucao_ms={duracao_total_ms})")

if __name__ == "__main__":
    main()
