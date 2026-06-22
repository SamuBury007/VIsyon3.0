FROM python:3.11-slim

# Installazione completa di tutte le dipendenze grafiche per Chromium e Playwright
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
    libxfixes3 \
    libxcursor1 \
    libxi6 \
    libxtst6 \
    libxrender1 \
    libxss1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Installa solo Chromium (ottimizzato per la RAM di Render)
RUN python -m playwright install chromium

ENV PORT=8080
EXPOSE 8080

# Avvio con Gunicorn (1 worker e 2 thread per evitare Out of Memory)
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "2", "--timeout", "120", "app:app"]
