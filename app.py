import io, os, re, zipfile
from urllib.parse import urlparse
import requests
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
CLIENT_ID = os.getenv('SOUNDCLOUD_CLIENT_ID', '').strip()
OAUTH_TOKEN = os.getenv('SOUNDCLOUD_OAUTH_TOKEN', '').strip()
MAX_TRACKS = max(1, min(int(os.getenv('MAX_TRACKS_PER_ZIP', '50')), 100))
MAX_AUDIO_MB = max(1, min(int(os.getenv('MAX_AUDIO_MB', '50')), 100))
API = 'https://api.soundcloud.com'
S = requests.Session()
S.headers['User-Agent'] = 'SCloud-Playlist-to-ZIP/1.0'

class AppError(Exception): pass

def valid_url(url):
    url = (url or '').strip()
    p = urlparse(url)
    if p.scheme not in ('http', 'https') or p.hostname not in ('soundcloud.com', 'www.soundcloud.com', 'm.soundcloud.com', 'on.soundcloud.com'):
        raise AppError('Masukkan URL SoundCloud yang valid.')
    if p.hostname == 'on.soundcloud.com':
        raise AppError('Link pendek on.soundcloud.com belum didukung. Buka link itu di browser, lalu salin URL playlist penuh dari soundcloud.com.')
    if not CLIENT_ID:
        raise AppError('Server belum dikonfigurasi. Admin harus memasukkan SOUNDCLOUD_CLIENT_ID dari akses API SoundCloud resmi.')
    return url

def api_get(url, params=None, stream=False):
    params = dict(params or {})
    params['client_id'] = CLIENT_ID
    headers = {}
    if OAUTH_TOKEN:
        headers['Authorization'] = 'OAuth ' + OAUTH_TOKEN
    try:
        r = S.get(url, params=params, headers=headers, timeout=(10, 35), stream=stream, allow_redirects=True)
    except requests.RequestException:
        raise AppError('Tidak dapat menghubungi SoundCloud. Coba lagi nanti.')
    if r.status_code in (401, 403):
        raise AppError('SoundCloud menolak akses API. Periksa izin aplikasi dan token resmi. Pembatasan tidak akan dilewati.')
    if r.status_code == 404:
        raise AppError('Playlist tidak ditemukan atau tidak dapat diakses.')
    if r.status_code == 429:
        raise AppError('Batas permintaan API tercapai. Tunggu sebentar lalu coba lagi.')
    if not r.ok:
        raise AppError(f'API SoundCloud mengembalikan status {r.status_code}. Periksa konfigurasi API.')
    return r

def resolve(url):
    data = api_get(API + '/resolve', {'url': url}).json()
    if not isinstance(data, dict) or not isinstance(data.get('tracks'), list):
        raise AppError('URL tidak mengarah ke playlist yang bisa dibaca melalui API resmi.')
    return data

def clean(s, fallback):
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', str(s or '')).strip(' .')
    s = re.sub(r'\s+', ' ', s)
    return (s[:120] or fallback)

def track_list(pl):
    result = []
    for t in (pl.get('tracks') or [])[:MAX_TRACKS]:
        if not isinstance(t, dict): continue
        user = t.get('user') or {}
        result.append({'id': t.get('id'), 'title': t.get('title') or 'Untitled',
                       'artist': user.get('username') or 'Unknown artist',
                       'permalink_url': t.get('permalink_url') or '',
                       'downloadable': bool(t.get('downloadable'))})
    return result

@app.get('/')
def home(): return render_template('index.html', max_tracks=MAX_TRACKS)

@app.get('/health')
def health(): return jsonify(ok=True)

@app.post('/api/playlist')
def playlist():
    try:
        data = request.get_json(silent=True) or {}
        pl = resolve(valid_url(data.get('url')))
        tracks = track_list(pl)
        return jsonify(title=pl.get('title') or 'SoundCloud playlist', user=(pl.get('user') or {}).get('username', 'Unknown'),
                       count=len(tracks), max_tracks=MAX_TRACKS, downloadable_count=sum(t['downloadable'] for t in tracks), tracks=tracks)
    except AppError as e: return jsonify(error=str(e)), 400
    except (ValueError, requests.RequestException): return jsonify(error='Respons API tidak valid.'), 502

@app.post('/api/zip')
def make_zip():
    try:
        data = request.get_json(silent=True) or {}
        pl = resolve(valid_url(data.get('url')))
        tracks = track_list(pl)
        allowed = [t for t in tracks if t['downloadable'] and t['id']]
        if not allowed: raise AppError('Tidak ada lagu yang ditandai downloadable oleh API resmi.')
        out = io.BytesIO(); added = 0; skipped = 0
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
            for n, t in enumerate(allowed, 1):
                try:
                    r = api_get(f"{API}/tracks/{t['id']}/download", stream=True)
                    content_type = (r.headers.get('Content-Type') or '').lower()
                    if 'text/html' in content_type or 'json' in content_type:
                        r.close(); skipped += 1; continue
                    data_bytes = bytearray(); limit = MAX_AUDIO_MB * 1024 * 1024
                    too_big = False
                    for chunk in r.iter_content(65536):
                        if chunk:
                            data_bytes.extend(chunk)
                            if len(data_bytes) > limit:
                                too_big = True; break
                    r.close()
                    if too_big or not data_bytes:
                        skipped += 1; continue
                    ext = '.ogg' if 'ogg' in content_type else ('.wav' if 'wav' in content_type else '.mp3')
                    filename = f"{n:03d} - {clean(t['artist'], 'Artist')} - {clean(t['title'], 'Track')}{ext}"
                    zf.writestr(filename, bytes(data_bytes)); added += 1
                except (AppError, requests.RequestException, OSError):
                    skipped += 1
        if not added: raise AppError('Tidak ada audio yang berhasil diunduh lewat endpoint resmi. Pastikan API/token memiliki izin download.')
        out.seek(0)
        resp = send_file(out, mimetype='application/zip', as_attachment=True, download_name=clean(pl.get('title'), 'soundcloud-playlist') + '.zip')
        resp.headers['X-Tracks-Added'] = str(added); resp.headers['X-Tracks-Skipped'] = str(skipped)
        return resp
    except AppError as e: return jsonify(error=str(e)), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '8080')), debug=False)
