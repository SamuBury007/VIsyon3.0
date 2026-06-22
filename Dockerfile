FROM python:3.11-slim

# Installazione di tutte le librerie Linux necessarie a Chromium (incluso libxkbcommon)
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
    libxkbcommon0 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# Installa pacchetti python
RUN pip install --no-cache-dir -r requirements.txt

# Installa solo l'eseguibile Chromium di Playwright per salvare RAM su Render
RUN python -m playwright install chromium

ENV PORT=8080
EXPOSE 8080

# Avvia l'applicazione direttamente tramite Python come richiesto dalla tua logica strutturale
CMD ["python", "app.py"]
