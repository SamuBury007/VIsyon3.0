#!/usr/bin/env bash
set -e

# Aggiorna pip e installa i pacchetti Python
pip install --upgrade pip
pip install -r requirements.txt

# Installa SOLO il binario di Chromium senza i pacchetti di sistema (APT)
playwright install chromium
