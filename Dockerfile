FROM python:3.11-slim

# install dipendenze di sistema per Playwright
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

# install python deps
RUN pip install --no-cache-dir -r requirements.txt

# install browser playwright
RUN python -m playwright install --with-deps

EXPOSE 8080

CMD ["python", "app.py"]
