#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Load environment variables from .env if present (non-fatal if missing)
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed and available on your PYTHONPATH environment variable."
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
