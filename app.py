#!/usr/bin/env python3
"""
VixSrc M3U8 Extractor v9.1 - Fixed Proxy Auth & Playwright Context
"""

import os
import sys
import uuid
import asyncio
import base64
import re
from urllib.parse import quote, urljoin
from flask import Flask, request, jsonify, render_template_string, Response, stream_with_context
import requests as req_lib

app = Flask(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

PROXY_HOST = os.environ.get("WEBSHARE_HOST", "p.webshare.io")
PROXY_PORT = os.environ.get("WEBSHARE_PORT", "80")
PROXY_USER = os.environ.get("WEBSHARE_USER", "")
PROXY_PASS = os.environ.get("WEBSHARE_PASS", "")

PROXY_SESSION = str(uuid.uuid4())[:8]

def _sticky_user():
    if not PROXY_USER:
        return ""
    base = PROXY_USER.replace("-rotate", "")
    return f"{base}-rotate-session-{PROXY_SESSION}"

def get_proxy_config():
    if PROXY_USER and PROXY_PASS:
        return {
            "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
            "username": _sticky_user(),
            "password": PROXY_PASS,
        }
    return None

def get_requests_proxies():
    if PROXY_USER and PROXY_PASS:
        proxy_url = f"http://{_sticky_user()}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        return {"http": proxy_url, "https": proxy_url}
    return None


async def extract_playlist_url(movie_url):
    playlist_urls = []
    all_requests = []  

    from playwright.async_api import async_playwright

    proxy = get_proxy_config()

    async with async_playwright() as p:
        launch_args = {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-web-security",
                "--allow-running-insecure-content",
            ]
        }
        if proxy:
            launch_args["proxy"] = {
                "server": proxy["server"],
                "username": proxy["username"],
                "password": proxy["password"]
            }
            print(f"[*] Proxy Lancio Browser: {proxy['server']} user={proxy['username']}", flush=True)
        else:
            print("[!] Nessun proxy configurato", flush=True)

        browser = await p.chromium.launch(**launch_args)
        
        # Argomenti del contesto (Cruciale reinserire le credenziali proxy qui)
        context_args = {
            "user_agent": USER_AGENT,
            "viewport": {"width": 1280, "height": 720},
            "ignore_https_errors": True,
        }
        if proxy:
            context_args["proxy"] = {
                "server": proxy["server"],
                "username": proxy["username"],
                "password": proxy["password"]
            }

        context = await browser.new_context(**context_args)

        # Intercettazione delle richieste di rete
        async def on_request(req):
            url = req.url
            if any(x in url for x in ["vixsrc", "playlist", "m3u8", "stream", "video", "cdn", "hls"]):
                print(f"  REQ: {url[:120]}", flush=True)
                all_requests.append(url)

            if "/playlist/" in url and "vixsrc.to" in url:
                if url not in playlist_urls:
                    playlist_urls.append(url)
                    print(f"[+] PLAYLIST TROVATA: {url}", flush=True)
            if "m3u8" in url:
                if url not in playlist_urls:
                    playlist_urls.append(url)
                    print(f"[+] M3U8 TROVATA: {url}", flush=True)

        async def on_response(resp):
            url = resp.url
            status = resp.status
            ct = resp.headers.get("content-type", "")
            if any(x in url for x in ["vixsrc", "playlist", "m3u8", "stream", "hls"]):
                print(f"  RESP {status}: {url[:120]} [{ct}]", flush=True)
            if ("/playlist/" in url and "vixsrc.to" in url) or "m3u8" in url or "mpegurl" in ct:
                if url not in playlist_urls:
                    playlist_urls.append(url)
                    print(f"[+] TROVATA (resp): {url}", flush=True)

        context.on("request", on_request)
        context.on("response", on_response)

        page = await context.new_page()

        print(f"[*] Caricamento pagina: {movie_url}", flush=True)
        try:
            await page.goto(movie_url, wait_until="domcontentloaded", timeout=30000)
            print(f"[*] Pagina caricata (domcontentloaded)", flush=True)
        except Exception as e:
            print(f"[-] Errore page.goto: {e}", flush=True)

        # Ciclo di attesa asincrono del player
        print("[*] In attesa del player...", flush=True)
        for i in range(50):
            await asyncio.sleep(1)
            if playlist_urls:
                print(f"[+] Link trovati dopo {i+1}s: {len(playlist_urls)}", flush=True)
                await asyncio.sleep(2)
                break
            if i == 10:
                try:
                    title = await page.title()
                    print(f"[*] @10s - Titolo: '{title}' URL attuale: {page.url}", flush=True)
                    await page.click(".play-button, .jw-icon-playback, button[aria-label='Play'], .vjs-play-control", timeout=1500)
                    print("[*] Tentativo click pulsante Play eseguito", flush=True)
                except:
                    pass
            if i == 20:
                try:
                    content = await page.content()
                    if any(x in content.lower() for x in ["cloudflare", "challenge", "just a moment"]):
                        print("[-] RILEVATO BLOCCO CLOUDFLARE CHALLENGE!", flush=True)
                    else:
                        print("[*] Pagina VixSrc accessibile senza blocchi visibili", flush=True)
                    
                    ss = await page.screenshot(type="jpeg", quality=30)
                    b64 = base64.b64encode(ss).decode()
                    print(f"[SCREENSHOT_B64]{b64}[/SCREENSHOT_B64]", flush=True)
                except Exception as e:
                    print(f"[-] Errore diagnostica @20s: {e}", flush=True)
            if i % 10 == 9:
                print(f"[.] {i+1}s passato - nessun link catturato...", flush=True)

        # Scansione di backup del codice HTML nei frame
        try:
            for frame in page.frames:
                try:
                    f_content = await frame.content()
                    matches = re.findall(r'https?://[^\s\'"<>]+(?:playlist|m3u8)[^\s\'"<>]*', f_content)
                    for u in matches:
                        if u not in playlist_urls:
                            playlist_urls.append(u)
                            print(f"[+] Trovato regex da sorgente frame HTML: {u}", flush=True)
                except:
                    pass
        except Exception as e:
            print(f"[-] Errore frame scan: {e}", flush=True)

        await browser.close()

    return playlist_urls


async def get_best_playlist(movie_url):
    urls = await extract_playlist_url(movie_url)
    if not urls:
        return None

    print(f"[*] Elenco totale link estratti ({len(urls)}):", flush=True)
    for u in urls:
        print(f"   {u}", flush=True)

    vixsrc = [u for u in urls if "vixsrc.to/playlist/" in u]
    pool = vixsrc if vixsrc else urls

    for q in ["1080p", "1080", "720p", "720", "480"]:
        match = [u for u in pool if q in u]
        if match:
            return match[0]

    return pool[0]


# ============================================================
# Flask Endpoints
# ============================================================

@app.route('/check-ip')
def check_ip():
    proxies = get_requests_proxies()
    proxy = get_proxy_config()

    results = {"proxy_attivo": proxy is not None, "session_id": PROXY_SESSION}

    if proxy:
        results["proxy_server"] = proxy["server"]
        results["proxy_user"] = proxy["username"]

    # Test con proxy
    try:
        r = req_lib.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
        results["ip_via_proxy"] = r.json()
    except Exception as e:
        results["ip_via_proxy_error"] = str(e)

    # Test senza proxy
    try:
        r2 = req_lib.get("https://api.ipify.org?format=json", timeout=10)
        results["ip_server_diretto"] = r2.json()
    except Exception as e:
        results["ip_server_diretto_error"] = str(e)

    return jsonify(results)


@app.route('/debug-page')
def debug_page():
    url = request.args.get('url', 'https://vixsrc.to/movie/786892/')

    async def run():
        from playwright.async_api import async_playwright
        proxy = get_proxy_config()
        async with async_playwright() as p:
            launch_args = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
            }
            if proxy:
                launch_args["proxy"] = {
                    "server": proxy["server"],
                    "username": proxy["username"],
                    "password": proxy["password"]
                }
            browser = await p.chromium.launch(**launch_args)
            
            context_args = {"user_agent": USER_AGENT, "ignore_https_errors": True}
            if proxy:
                context_args["proxy"] = {
                    "server": proxy["server"],
                    "username": proxy["username"],
                    "password": proxy["password"]
                }
            
            context = await browser.new_context(**context_args)
            page = await context.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(5)
                title = await page.title()
                final_url = page.url
                content = await page.content()
                is_cf = any(x in content.lower() for x in ["cloudflare", "just a moment"])
                ss = await page.screenshot(type="jpeg", quality=40)
                ss_b64 = base64.b64encode(ss).decode()
            except Exception as e:
                title = f"ERRORE RUNTIME: {e}"
                final_url = url
                is_cf = False
                ss_b64 = ""
            await browser.close()
            return {"title": title, "final_url": final_url, "cloudflare_blocked": is_cf, "screenshot_b64": ss_b64[:500] + "..." if ss_b64 else ""}

    loop = asyncio.new_event_loop()
    result = loop.run_until_complete(run())
    loop.close()
    return jsonify(result)


@app.route('/proxy')
def proxy_stream():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({'error': 'Parametro url mancante'}), 400

    proxies = get_requests_proxies()
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://vixsrc.to/",
        "Origin": "https://vixsrc.to",
    }

    try:
        r = req_lib.get(target_url, headers=headers, proxies=proxies, stream=True, timeout=30)
        content_type = r.headers.get('Content-Type', '')

        if 'mpegurl' in content_type or 'm3u8' in content_type or '.m3u8' in target_url:
            content = r.text
            base = request.host_url.rstrip('/')
            def rewrite(line):
                line = line.strip()
                if line.startswith('http://') or line.startswith('https://'):
                    return f"{base}/proxy?url={quote(line, safe='')}"
                elif line and not line.startswith('#'):
                    abs_url = urljoin(target_url, line)
                    return f"{base}/proxy?url={quote(abs_url, safe='')}"
                return line
            rewritten = "\n".join(rewrite(l) for l in content.splitlines())
            return Response(rewritten, content_type='application/vnd.apple.mpegurl')

        return Response(
            stream_with_context(r.iter_content(chunk_size=65536)),
            content_type=r.headers.get('Content-Type', 'application/octet-stream'),
            status=r.status_code,
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/extract', methods=['POST'])
def api_extract():
    data = request.get_json() or {}
    movie_url = data.get('url', '')

    if not movie_url:
        return jsonify({'success': False, 'error': 'URL obbligatorio'})

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        playlist_url = loop.run_until_complete(get_best_playlist(movie_url))
        loop.close()

        if playlist_url:
            base = request.host_url.rstrip('/')
            proxied_url = f"{base}/proxy?url={quote(playlist_url, safe='')}"
            return jsonify({'success': True, 'url': proxied_url, 'original': playlist_url})
        else:
            return jsonify({'success': False, 'error': 'Nessun link m3u8 individuato. Controlla i log di Render e le rotte di diagnostica.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>VixSrc Playlist Extractor</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0f0f0f; color: #e0e0e0; line-height: 1.6; }
        .container { max-width: 800px; margin: 50px auto; padding: 0 20px; }
        h1 { color: #00d4aa; font-size: 1.8em; margin-bottom: 6px; }
        .subtitle { color: #888; margin-bottom: 30px; }
        .card { background: #1a1a2e; border-radius: 12px; padding: 30px; border: 1px solid #2a2a4a; }
        label { display: block; margin-bottom: 8px; color: #aaa; font-size: 0.9em; }
        input[type=text] { width: 100%; padding: 12px 16px; background: #0f0f1a;
                           border: 1px solid #333; border-radius: 8px; color: #fff;
                           font-size: 1em; margin-bottom: 15px; }
        input[type=text]:focus { outline: none; border-color: #00d4aa; }
        .main-btn { background: #00d4aa; color: #000; border: none; padding: 12px 24px;
                    border-radius: 8px; font-size: 1em; font-weight: 600; cursor: pointer; }
        .main-btn:hover { background: #00f0c0; }
        .debug-links { margin-top: 20px; font-size: 0.82em; color: #555; }
        .debug-links a { color: #00d4aa; margin-right: 12px; }
        .result { margin-top: 20px; padding: 15px; background: #0f0f1a; border-radius: 8px;
                  border: 1px solid #2a2a4a; word-break: break-all; display: none; }
        .result.success { border-color: #00d4aa; display: block; }
        .result.error { border-color: #ff4444; display: block; }
        .result code { color: #00d4aa; font-size: 0.85em; }
        .loader { display: none; margin: 15px 0; color: #888; }
        .loader.active { display: block; }
        .spinner { display: inline-block; width: 18px; height: 18px; border: 3px solid #333;
                   border-top: 3px solid #00d4aa; border-radius: 50%;
                   animation: spin 0.8s linear infinite; margin-right: 8px; vertical-align: middle; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .copy-btn { background: #333; color: #fff; border: none; padding: 6px 14px;
                    border-radius: 4px; cursor: pointer; font-size: 0.85em; margin-left: 8px; }
        .copy-btn:hover { background: #444; }
        .note { color: #666; font-size: 0.82em; margin-top: 10px; }
        .orig { color: #555; font-size: 0.75em; margin-top: 8px; word-break: break-all; }
    </style>
</head>
<body>
    <div class="container">
        <h1>VixSrc Playlist Extractor</h1>
        <p class="subtitle">Incolla il link del film, ottieni il link M3U8 da usare in VLC</p>
        <div class="card">
            <label for="url-input">URL del film su vixsrc.to</label>
            <input type=text id="url-input" placeholder="https://vixsrc.to/movie/786892/" />
            <button class="main-btn" id="extract-btn">Estrai Link Playlist</button>
            <div class="loader" id="loader">
                <span class="spinner"></span> Estrazione in corso (30-60 secondi)...
            </div>
            <div class="result" id="result"></div>
            <div class="debug-links">
                Diagnostica: <a href="/check-ip" target="_blank">/check-ip</a>
                <a href="/debug-page" target="_blank">/debug-page</a>
            </div>
        </div>
    </div>
    <script>
        function copyUrl() {
            var url = document.getElementById('playlisturl').textContent;
            navigator.clipboard.writeText(url).then(function() {
                var btn = document.querySelector('.copy-btn');
                btn.textContent = 'Copiato!';
                setTimeout(function() { btn.textContent = 'Copia'; }, 2000);
            });
        }
        function extract() {
            var url = document.getElementById('url-input').value.trim();
            if (!url) {
                document.getElementById('result').className = 'result error';
                document.getElementById('result').innerHTML = 'Inserisci un URL valido';
                return;
            }
            document.getElementById('loader').className = 'loader active';
            document.getElementById('result').className = 'result';
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/extract');
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.timeout = 120000;
            xhr.onload = function() {
                document.getElementById('loader').className = 'loader';
                var data = JSON.parse(xhr.responseText);
                if (data.success) {
                    document.getElementById('result').className = 'result success';
                    document.getElementById('result').innerHTML =
                        '<strong>Playlist trovata!</strong><br><br>' +
                        '<span style="color:#888">Copia e incolla in VLC (Ctrl+N):</span><br><br>' +
                        '<code id="playlisturl">' + data.url + '</code>' +
                        '<button class="copy-btn" onclick="copyUrl()">Copia</button><br><br>' +
                        '<span class="note">In VLC: Ctrl+N > incolla URL > Play</span>' +
                        (data.original ? '<div class="orig">Originale: ' + data.original + '</div>' : '');
                } else {
                    document.getElementById('result').className = 'result error';
                    document.getElementById('result').innerHTML = 'Errore: ' + data.error;
                }
            };
            xhr.onerror = function() {
                document.getElementById('loader').className = 'loader';
                document.getElementById('result').className = 'result error';
                document.getElementById('result').innerHTML = 'Errore di rete generico';
            };
            xhr.ontimeout = function() {
                document.getElementById('loader').className = 'loader';
                document.getElementById('result').className = 'result error';
                document.getElementById('result').innerHTML = 'Timeout elaborazione server superato (120s)';
            };
            xhr.send(JSON.stringify({ url: url }));
        }
        document.getElementById('extract-btn').onclick = extract;
        document.getElementById('url-input').onkeydown = function(e) {
            if (e.key === 'Enter') extract();
        };
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    print(f"[*] Avvio Server con Session ID Proxy: {PROXY_SESSION}", flush=True)
    if len(sys.argv) > 1:
        async def main():
            url = await get_best_playlist(sys.argv[1])
            print(f"\n[+] Link Risultato: {url}" if url else "\n[-] Nessun link trovato via CLI")
        asyncio.run(main())
    else:
        app.run(host='0.0.0.0', port=port, debug=False)
