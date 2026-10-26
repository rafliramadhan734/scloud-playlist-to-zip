# SCloud Playlist to ZIP

Website Flask dengan desain mobile-first. Memakai API SoundCloud resmi; tidak melakukan scraping, ripping stream, atau bypass pembatasan.

## Sebelum digunakan
Aplikasi memerlukan `SOUNDCLOUD_CLIENT_ID` dari aplikasi/API SoundCloud yang terdaftar dan diizinkan. Pengunduhan dapat memerlukan OAuth token resmi. Tidak semua akun/aplikasi mendapat akses API atau izin mengunduh audio. Jika endpoint download tidak diizinkan oleh SoundCloud, proses akan gagal dengan pesan dan tidak mencoba cara alternatif.

Link pendek `https://on.soundcloud.com/...` perlu dibuka di browser, kemudian salin URL playlist penuh dari `soundcloud.com`.

## Jalankan di Android Termux
```bash
pkg update -y
pkg install python git unzip -y
cd ~/scloud-playlist-to-zip
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export SOUNDCLOUD_CLIENT_ID='CLIENT_ID_RESMI'
# Hanya jika API resmi memerlukan token OAuth:
export SOUNDCLOUD_OAUTH_TOKEN='OAUTH_TOKEN_RESMI'
python app.py
```
Buka `http://127.0.0.1:8080` pada browser HP.

## Hosting online dengan Render
1. Buat repo GitHub kosong dan unggah semua file proyek kecuali `.env`/token.
2. Di Render pilih **New → Web Service**, hubungkan repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --workers 2 --threads 4 --timeout 180`
5. Tambahkan `SOUNDCLOUD_CLIENT_ID` dan, bila diperlukan oleh akses resmi, `SOUNDCLOUD_OAUTH_TOKEN` di Environment Variables Render.
6. Deploy. URL Render dapat dibagikan ke teman.

Jangan memasukkan token ke HTML atau repo publik. Hosting gratis dapat tidur, punya batas RAM, dan tidak cocok untuk arsip audio besar. Nilai default membatasi playlist ke 50 lagu dan setiap audio ke 50 MB.

## Catatan kompatibilitas
SoundCloud mengatur ketersediaan API dan download. Field `downloadable` atau endpoint download dapat berubah atau memerlukan izin tambahan; ini bukan jaminan bahwa setiap lagu playlist bisa diunduh. Gunakan hanya audio yang kamu punya hak untuk mengunduh.
