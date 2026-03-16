import random

def get_random_profile():
    """
    Retorna perfis de navegação padronizados e consistentes.
    Mantém versões de browser próximas e resoluções de tela comuns.
    """
    profiles = [
        {
            "name": "Windows_Chrome_Standard",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
            "locale": "pt-BR",
            "timezone_id": "America/Sao_Paulo"
        },
        {
            "name": "Windows_Edge_Common",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            "viewport": {"width": 1366, "height": 768},
            "locale": "pt-BR",
            "timezone_id": "America/Sao_Paulo"
        },
        {
            "name": "MacBook_Chrome_Standard",
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "viewport": {"width": 1440, "height": 900},
            "locale": "pt-BR",
            "timezone_id": "America/Sao_Paulo"
        }
    ]
    
    return random.choice(profiles)