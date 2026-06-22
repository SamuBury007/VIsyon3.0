#!/usr/bin/env python3
"""
VixSrc M3U8 Extractor v4 - VISYON Backend (Render + Docker Ready)
"""

import re
import sys
import json
import asyncio
import requests
import os
from urllib.parse import urlparse, parse_qs, urlencode
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 🔥 FIX CORS per Netlify

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ============================================================
# PLAYWRIGHT SCRAPER
# ============================================================

async def extract_playlist_url(movie_url):
    playlist_urls = []

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 720}
        )

        page = await context.new_page()

        async def handle_request(request):
            url = request.url

            if "/playlist/" in url and "vixsrc.to" in url:
                if url not in playlist_urls:
                    playlist_urls.append(url)

            if "playlist" in url and "m3u8" in url:
                if url not in playlist_urls:
                    playlist_urls.append(url)

        async def handle_response(response):
            url = response.url
            if "/playlist/" in url and "vixsrc.to" in url:
                if url not in playlist_urls:
                    playlist_urls.append(url)

        page.on("request", handle_request)
        page.on("response", handle_response)

        try:
            await page.goto(movie_url, wait_until="networkidle", timeout=30000)

            for _ in range(10):
                await asyncio.sleep(1)
                if playlist_urls:
                    break

        except Exception:
            await asyncio.sleep(3)

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
        if r.status_code == 200:
            return r.text
    except:
        pass
    return None


def _playlist_has_audio(content):
    if not content:
        return False
    content = content.upper()
    return "EXT-X-MEDIA:TYPE=AUDIO" in content or "MP4A" in content


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

    master_with_audio = None
    any_with_audio = None

    for u in candidates:
        content = _fetch_m3u8(u, referer=movie_url)
        if not content:
            continue

        has_audio = _playlist_has_audio(content)
        is_master = _is_master_playlist(content)

        if has_audio and not any_with_audio:
            any_with_audio = u

        if has_audio and is_master:
            master_with_audio = u
            break

    if master_with_audio:
        return master_with_audio

    if any_with_audio:
        return any_with_audio

    return candidates[0] if candidates else None


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template("visyon.html")


@app.route("/extract", methods=["POST"])
def api_extract():
    data = request.get_json()
    movie_url = data.get("url", "")

    if not movie_url:
        return jsonify({"success": False, "error": "URL richiesto"})

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        playlist_url = loop.run_until_complete(get_best_playlist(movie_url))

        loop.close()

        if playlist_url:
            return jsonify({
                "success": True,
                "url": playlist_url
            })

        return jsonify({"success": False, "error": "Nessun link trovato"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ============================================================
# START SERVER (RENDER READY)
# ============================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # 🔥 IMPORTANTE PER RENDER

    app.run(
        host="0.0.0.0",
        port=port
    )