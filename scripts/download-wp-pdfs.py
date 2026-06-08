"""
Télécharge les 48 PDFs hébergés sur levangileduroyaume.com (WordPress)
vers scripts/pdf-downloads/ pour upload sur Backblaze B2.

Usage :
    python3 scripts/download-wp-pdfs.py

Les fichiers sont nommés : livres_<id>_<nom>.pdf  /  articles_<id>_<nom>.pdf
"""

import json
import os
import time
import urllib.request
import urllib.error

# ── Configuration ──────────────────────────────────────────────
BOOKS_JSON    = 'assets/data/books.json'
ARTICLES_JSON = 'assets/data/articles.json'
OUTPUT_DIR    = 'scripts/pdf-downloads'
PAUSE_SECONDS = 0.6   # Délai entre requêtes pour ne pas surcharger le serveur

# ── Collecte des URLs ──────────────────────────────────────────
def collect_pdfs():
    pdfs = []

    with open(BOOKS_JSON, 'r', encoding='utf-8') as f:
        books = json.load(f)
    for b in books:
        if b.get('pdf') and b['pdf'].startswith('http'):
            filename_raw = b['pdf'].split('/')[-1]
            filename = f"livres_{b['id']}_{filename_raw}"
            pdfs.append({'url': b['pdf'], 'filename': filename, 'title': b['title'], 'id': b['id'], 'type': 'livre'})

    with open(ARTICLES_JSON, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    for a in articles:
        if a.get('pdf') and a['pdf'].startswith('http'):
            filename_raw = a['pdf'].split('/')[-1]
            filename = f"articles_{a['id']}_{filename_raw}"
            pdfs.append({'url': a['pdf'], 'filename': filename, 'title': a['title'], 'id': a['id'], 'type': 'article'})

    return pdfs

# ── Téléchargement ─────────────────────────────────────────────
def download_pdf(url, dest_path):
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/pdf,*/*'
        }
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        content = response.read()
    with open(dest_path, 'wb') as f:
        f.write(content)
    return len(content)

# ── Main ───────────────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdfs = collect_pdfs()

    print(f'📄 {len(pdfs)} PDFs à télécharger → {OUTPUT_DIR}/')
    print()

    ok = 0
    errors = []

    for i, item in enumerate(pdfs, 1):
        dest = os.path.join(OUTPUT_DIR, item['filename'])

        # Reprendre si déjà téléchargé
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            size_kb = os.path.getsize(dest) // 1024
            print(f'  [{i:02d}/{len(pdfs)}] ⏭  déjà présent ({size_kb} KB) — {item["filename"]}')
            ok += 1
            continue

        try:
            size = download_pdf(item['url'], dest)
            size_kb = size // 1024
            print(f'  [{i:02d}/{len(pdfs)}] ✓  {size_kb} KB — {item["filename"]}')
            ok += 1
        except Exception as e:
            print(f'  [{i:02d}/{len(pdfs)}] ✗  ERREUR — {item["filename"]}')
            print(f'       {e}')
            errors.append({'filename': item['filename'], 'url': item['url'], 'error': str(e)})

        time.sleep(PAUSE_SECONDS)

    print()
    print(f'═══ Résultat : {ok}/{len(pdfs)} téléchargés ═══')

    if errors:
        print(f'\n⚠  {len(errors)} erreur(s) :')
        for e in errors:
            print(f'   ✗ {e["filename"]}')
            print(f'     URL : {e["url"]}')
            print(f'     Err : {e["error"]}')

    # Récapitulatif des tailles
    total_bytes = sum(
        os.path.getsize(os.path.join(OUTPUT_DIR, f))
        for f in os.listdir(OUTPUT_DIR) if f.endswith('.pdf')
    )
    print(f'\nTaille totale : {total_bytes / 1024 / 1024:.1f} MB')
    print(f'\nDossier : {os.path.abspath(OUTPUT_DIR)}')
    print('\nÉtape suivante :')
    print('  1. Créer un bucket Backblaze B2 (ex: "pdfs-site-web"), le passer en Public')
    print('  2. Uploader tout le contenu de pdf-downloads/ dans ce bucket')
    print('  3. Revenir ici pour mettre à jour books.json et articles.json avec les nouvelles URLs')

if __name__ == '__main__':
    main()
