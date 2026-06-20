#!/usr/bin/env bash
set -e

# Aggiorna pip e installa i pacchetti Python requisiti
pip install --upgrade pip
pip install -r requirements.txt

# Installa il browser Chromium e tutte le librerie di sistema Linux necessarie per farlo girare headless
playwright install chromium
playwright install-deps chromium
