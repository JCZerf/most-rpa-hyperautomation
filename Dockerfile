FROM python:3.12-slim

WORKDIR /app

# Defina caminho fixo para os browsers do Playwright (funciona em runtime e build)
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Instala dependências do sistema para Playwright/Chromium
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libexpat1 \
    libfontconfig1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Copia requisitos primeiro para aproveitar cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instala browsers do Playwright
RUN playwright install --with-deps chromium

# Copia o código
COPY . .

# Porta padrão para Cloud Run (ajusta via env PORT)
EXPOSE 8080

# Comando padrão: gunicorn lendo a porta do ambiente (fallback 8000 para dev local)
CMD ["sh", "-c", "gunicorn web.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1"]
