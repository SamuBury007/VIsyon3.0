FROM python:3.11-slim

# Installazione dipendenze di sistema minime per Playwright e Chromium
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    libglib2.0-0 \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libxshmfence1 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libharfbuzz0b \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Installa SOLO chromium per Playwright (risparmia spazio e RAM)
RUN python -m playwright install chromium

# Variabile d'ambiente per forzare la porta se necessario
ENV PORT=8080
EXPOSE 8080

# Usiamo gunicorn per la produzione su Render (1 worker è consigliato per evitare saturazione di RAM con Playwright)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--timeout", "120", "app:app"]
