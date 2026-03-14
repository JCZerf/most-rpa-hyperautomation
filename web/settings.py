import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'replace-me-in-production'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', SECRET_KEY)
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')
API_MASTER_KEY = os.getenv('API_MASTER_KEY')  # legado, manter para compatibilidade se necessário
API_TOKEN_TTL = int(os.getenv('API_TOKEN_TTL', '600'))
OAUTH_CLIENT_ID = os.getenv('OAUTH_CLIENT_ID')
OAUTH_CLIENT_SECRET = os.getenv('OAUTH_CLIENT_SECRET')
OAUTH_AUDIENCE = os.getenv('OAUTH_AUDIENCE', 'most-rpa-api')

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'rest_framework',
    'api',
    'drf_spectacular',
]

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Evita exibir basicAuth/cookieAuth no Swagger; autenticação é tratada via Bearer manualmente
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'TransparencyBot API',
    'DESCRIPTION': 'API para consultar robô de transparência',
    'VERSION': '1.0.0',
    'SERVERS': [
        {'url': 'http://127.0.0.1:8000', 'description': 'Local'},
    ],
    'SECURITY': [
        {'bearerAuth': []},
    ],
    'TAGS': [
        {'name': 'Auth', 'description': 'Autenticação OAuth2 (client_credentials)'},
        {'name': 'Consulta', 'description': 'Execução do robô de transparência'},
    ],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'bearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    },
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
        'tagsSorter': 'manual',
        'operationsSorter': 'alpha',
    },
}

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'web.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    }
]

WSGI_APPLICATION = 'web.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_L10N = False
USE_TZ = True

STATIC_URL = '/static/'
