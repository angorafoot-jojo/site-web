#!/usr/bin/env python3
"""
migrate_nav.py — Migre toutes les pages HTML pour utiliser nav.js centralisé.

Pour chaque page :
  1. Ajoute data-page="[name]" sur <body>
  2. Insère <script src="assets/js/nav.js"></script> en premier enfant du body
  3. Supprime le sprite SVG inline
  4. Supprime <header class="site-header">…</header>
  5. Supprime <nav class="mobile-menu"…>…</nav>
  6. Supprime <div class="mobile-overlay"…></div>
  7. Supprime <footer class="site-footer">…</footer>
"""

import re, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))

# page_name -> (fichier html, page slug pour data-page)
PAGES = {
    'index.html'         : 'index',
    'radio.html'         : 'radio',
    'audios.html'        : 'audios',
    'podcasts.html'      : 'podcasts',
    'videos.html'        : 'videos',
    'articles.html'      : 'articles',
    'livres.html'        : 'livres',
    'louange.html'       : 'louange',
    'contact.html'       : 'contact',
    'qui-sommes-nous.html': 'qui-sommes-nous',
    'confidentialite.html': 'confidentialite',
    'nospartenaires.html': 'nospartenaires',
    'nouveau.html'       : 'nouveau',
    '404.html'           : '404',
}


def remove_block(html: str, open_pattern: str, close_tag: str) -> str:
    """
    Supprime le premier bloc délimité par open_pattern (regex) et
    le close_tag correspondant (en comptant la profondeur d'imbrication).
    """
    m = re.search(open_pattern, html, re.IGNORECASE | re.DOTALL)
    if not m:
        return html

    start    = m.start()
    tag_name = close_tag.lstrip('</').rstrip('>')
    open_re  = re.compile(r'<' + re.escape(tag_name) + r'[\s>]', re.IGNORECASE)
    close_re = re.compile(r'</' + re.escape(tag_name) + r'>', re.IGNORECASE)

    # depth=1 : on a déjà consommé le tag d'ouverture
    depth = 1
    pos   = m.end()
    while pos < len(html):
        o = open_re.search(html, pos)
        c = close_re.search(html, pos)
        if not c:
            break
        if o and o.start() < c.start():
            depth += 1
            pos = o.end()
        else:
            depth -= 1
            if depth == 0:
                end = c.end()
                # Retire la ligne vide éventuelle après le bloc
                if end < len(html) and html[end] == '\n':
                    end += 1
                prefix = html[:start]
                suffix = html[end:]
                # Retire la ligne de commentaire HTML juste avant (ex: <!-- SVG Sprite inline -->)
                prefix = re.sub(r'\n?[ \t]*<!--[^>]*-->\s*$', '', prefix)
                return prefix + suffix
            else:
                pos = c.end()
    return html


def remove_line(html: str, pattern: str) -> str:
    """Supprime toutes les lignes correspondant au pattern (regex)."""
    return re.sub(r'[ \t]*' + pattern + r'[ \t]*\n?', '', html, flags=re.IGNORECASE)


def migrate(filename: str, page_slug: str) -> None:
    path = os.path.join(BASE, filename)
    if not os.path.exists(path):
        print(f'  ⚠  Fichier introuvable : {filename}')
        return

    with open(path, encoding='utf-8') as f:
        html = f.read()

    original = html

    # 1. Ajouter data-page sur <body> (sans écraser les attributs existants)
    if 'data-page=' not in html:
        html = re.sub(
            r'<body([^>]*)>',
            lambda m: f'<body{m.group(1)} data-page="{page_slug}">',
            html, count=1
        )
    else:
        html = re.sub(
            r'data-page="[^"]*"',
            f'data-page="{page_slug}"',
            html, count=1
        )

    # 2. Insérer le script nav.js comme premier enfant du body
    nav_tag = '<script src="assets/js/nav.js"></script>'
    if nav_tag not in html:
        html = re.sub(
            r'(<body[^>]*>)\s*',
            lambda m: m.group(1) + '\n<script src="assets/js/nav.js"></script>\n\n',
            html, count=1
        )

    # 3. Supprimer le sprite SVG inline
    html = remove_block(html, r'<svg[^>]+style="display:none"[^>]*>', '</svg>')

    # 4. Supprimer le header
    html = remove_block(html, r'<header\s+class="site-header"', '</header>')

    # 5. Supprimer le menu mobile
    html = remove_block(html, r'<nav\s+class="mobile-menu"', '</nav>')

    # 6. Supprimer l'overlay
    html = remove_line(html, r'<div\s+class="mobile-overlay"[^>]*/?>(?:</div>)?')

    # 7. Supprimer le footer (s'il existe)
    html = remove_block(html, r'<footer\s+class="site-footer"', '</footer>')

    # Nettoyage : éviter les lignes vides consécutives (>2)
    html = re.sub(r'\n{3,}', '\n\n', html)

    if html == original:
        print(f'  ─  {filename:<30} (aucun changement)')
        return

    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'  ✓  {filename}')


def main():
    print('\nMigration nav.js — démarrage\n')
    for filename, slug in PAGES.items():
        migrate(filename, slug)
    print('\nTerminé.\n')


if __name__ == '__main__':
    main()
