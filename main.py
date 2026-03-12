from pathlib import Path
import json

from bot.scraper import TransparencyBot


def main():
    bot = TransparencyBot(headless=False)
    resultado = bot.run()

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "result.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()