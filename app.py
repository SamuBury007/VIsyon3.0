#!/usr/bin/env python3
"""
VixSrc M3U8 Extractor v4 - VISYON Backend (Render + Docker Stable)
"""

import asyncio
import requests
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ============================================================
# PLAYWRIGHT SCRAPER
# ============================================================

async def extract_playlist_url(movie_url):
    playlist_urls = []
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )

        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720}
        )

        page = await context.new_page()

        async def handle_request(request):
            url = request.url
            if "playlist" in url or "m3u8" in url:
                if url not in playlist_urls:
                    playlist_urls.append(url)

        page.on("request", handle_request)

        try:
            await page.goto(movie_url, wait_until="networkidle", timeout=45000)

            for _ in range(20):
                await asyncio.sleep(1)
                if len(playlist_urls) > 0:
                    break
        except Exception:
            await asyncio.sleep(8)

        try:
            js_result = await page.evaluate("""
                () => {
                    const results = [];
                    document.querySelectorAll('script').forEach(s => {
                        const text = s.textContent || '';
                        const matches = text.match(/https?:\\/\\/[^'"\\s]*\\/playlist\\/[^'"\\s]*/g);
                        if (matches) results.push(...matches);
                    });
                    return [...new Set(results)];
                }
            """)

            for url in js_result:
                if url not in playlist_urls:
                    playlist_urls.append(url)
        except:
            pass

        await browser.close()

    return playlist_urls

# ============================================================
# M3U8 HELPERS
# ============================================================

def _fetch_m3u8(url, referer):
    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": referer,
                "Accept": "*/*",
            },
            timeout=10,
        )
        return r.text if r.status_code == 200 else None
    except:
        return None

def _playlist_has_audio(content):
    if not content:
        return False
    c = content.upper()
    return "EXT-X-MEDIA:TYPE=AUDIO" in c or "MP4A" in c

def _is_master_playlist(content):
    return content and "#EXT-X-STREAM-INF" in content.upper()

# ============================================================
# CORE LOGIC
# ============================================================

async def get_best_playlist(movie_url):
    urls = await extract_playlist_url(movie_url)
    if not urls:
        return None

    candidates = urls
    best = None
    fallback = None

    for u in candidates:
        content = _fetch_m3u8(u, movie_url)
        if not content:
            continue

        has_audio = _playlist_has_audio(content)
        is_master = _is_master_playlist(content)

        if has_audio and not fallback:
            fallback = u

        if has_audio and is_master:
            best = u
            break

    if best:
        return best
    if fallback:
        return fallback

    return candidates[0]

# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return jsonify({
        "status": "online",
        "service": "VISYON API"
    })

@app.route("/extract", methods=["POST"])
def api_extract():
    data = request.get_json() or {}
    movie_url = data.get("url", "")

    if not movie_url:
        return jsonify({"success": False, "error": "URL richiesto"}), 400

    try:
        # Modo pulito e sicuro per eseguire codice async dentro Flask in produzione
        result = asyncio.run(get_best_playlist(movie_url))

        if result:
            return jsonify({
                "success": True,
                "url": result
            })

        return jsonify({"success": False, "error": "Nessun link trovato"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
