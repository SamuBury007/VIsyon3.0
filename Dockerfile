# Installazione completa delle dipendenze di sistema per Chromium
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
