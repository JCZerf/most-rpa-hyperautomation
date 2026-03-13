import json
import logging
from pathlib import Path
from datetime import datetime
from bot.scraper import TransparencyBot

# Configura o logging para mostrar data, hora e o nível da mensagem
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_execution.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Iniciando o processo de automação...")
    
    # Instancia o bot. 
    bot = TransparencyBot(headless=True)
    
    try:
        # Executa a raspagem
        resultado = bot.run()
        
        if not resultado or "error" in resultado:
            logger.error("A automação falhou ou não retornou dados válidos.")
            return

        # Define diretórios e nomes de arquivos usando Pathlib de forma robusta
        out_dir = Path("output")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Opcional: Adiciona timestamp no nome do arquivo para não sobrescrever resultados anteriores
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_file = out_dir / f"result_{timestamp}.json"
        
        # Salva o JSON
        with out_file.open("w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=4)
        
        logger.info(f"Dados salvos com sucesso em: {out_file}")

    except Exception as e:
        logger.critical(f"Erro inesperado na função principal: {e}", exc_info=True)

if __name__ == "__main__":
    main()