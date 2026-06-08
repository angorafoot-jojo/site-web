#!/usr/bin/env python3
"""
Script de conversion PDF → EPUB pour les articles du site L'Évangile du Royaume.
Télécharge les PDFs depuis levangileduroyaume.com, extrait le texte,
le nettoie et génère des fichiers EPUB compatibles avec epub.js.
"""

import requests
import io
import re
import os
import PyPDF2
from ebooklib import epub

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "articles")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0"}

ARTICLES = [
    {
        "id": 1,
        "title": "Confession de la Parole de foi et de liberté",
        "pdf": "https://levangileduroyaume.com/wp-content/uploads/2024/07/CONFESSION-DE-LA-PAROLE-DE-FOI-ET-DE-LIBERTE-version-francaise.pdf",
        "lang": "fr",
    },
    {
        "id": 2,
        "title": "La grandeur de Dieu et la fragilité de l'homme",
        "pdf": "https://levangileduroyaume.com/wp-content/uploads/2024/07/LA-GRANDEUR-DE-DIEU-ET-LA-FRAGILITE-DE-LHOMME1.pdf",
        "lang": "fr",
    },
    {
        "id": 3,
        "title": "Le temps de remettre les choses en ordre",
        "pdf": "https://levangileduroyaume.com/wp-content/uploads/2024/06/LE-TEMPS-DE-REMETTRE-LES-CHOSES-EN-ORDRE.pdf",
        "lang": "fr",
    },
    {
        "id": 4,
        "title": "The Time of Putting All Things Straight",
        "pdf": "https://levangileduroyaume.com/wp-content/uploads/2024/06/THE-TIME-OF-PUTTING-ALL-THINGS-STRAIGHT.pdf",
        "lang": "en",
    },
    {
        "id": 5,
        "title": "Des Antichrists et du corps ayant la charge de les détruire",
        "pdf": "https://levangileduroyaume.com/wp-content/uploads/2024/06/DES-ANTICHRISTS-ET-DU-CORPS-AYANT-LA-CHARGE-DE-LES-DETRUIRE.pdf",
        "lang": "fr",
    },
    {
        "id": 6,
        "title": "Of Antichrists and of a Body That Destroys Them",
        "pdf": "https://levangileduroyaume.com/wp-content/uploads/2024/06/OF-ANTICHRISTS-AND-A-BODY-THAT-DESTROYS-THEM.pdf",
        "lang": "en",
    },
    {
        "id": 7,
        "title": "Le Combat Spirituel",
        "pdf": "https://levangileduroyaume.com/wp-content/uploads/2021/04/LE-COMBAT-SPIRITUEL.pdf",
        "lang": "fr",
    },
]


def clean_text(raw: str) -> str:
    """Nettoie le texte extrait d'un PDF."""
    # Supprimer les retours chariot Windows
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Corriger les mots fractionnés par un espace parasite (ex: "SPIRITUEL LE" → "SPIRITUELLE")
    # Détection: lettre majuscule suivie d'un espace puis lettre majuscule à l'intérieur d'un mot
    text = re.sub(r'([A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ])  +([A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ])', r'\1\2', text)

    # Supprimer les numéros de page (ex: "Page 3 sur 17", "- 3 -", "3\n")
    text = re.sub(r'Page\s+\d+\s+sur\s+\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # Supprimer les lignes de pied de page répétitives (email, site, etc.)
    text = re.sub(r'Email\s*:\s*\S+@\S+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Pour plus d.informations.*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"L.équipe de l.Évangile du Royaume", '', text)
    text = re.sub(r"L'ÉVANGILE DU ROYAUM?E?", '', text)
    text = re.sub(r'\[Cet article se veut.*?\]', '', text, flags=re.DOTALL)

    # Réduire les lignes vides multiples à maximum 2
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Supprimer les espaces en début/fin de ligne
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def text_to_html_sections(text: str, title: str) -> str:
    """Convertit le texte nettoyé en HTML structuré avec titres et paragraphes."""
    lines = text.split('\n')
    html_parts = []
    buffer = []

    def flush_buffer():
        if buffer:
            para = ' '.join(l for l in buffer if l).strip()
            if para:
                html_parts.append(f'<p>{para}</p>')
            buffer.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_buffer()
            continue

        # Détecter les titres : ligne toute en majuscules (avec accents) de 5+ caractères
        # ou ligne courte ≤ 80 chars qui semble un titre (commence par majuscule, pas de point final)
        is_heading = False

        # Titre majuscules : au moins 5 lettres, > 50% en majuscules
        letters = [c for c in stripped if c.isalpha()]
        if letters:
            ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if ratio > 0.6 and len(stripped) >= 5 and len(stripped) <= 120:
                is_heading = True

        if is_heading:
            flush_buffer()
            # Nettoyer les artefacts de mots fracturés dans les titres
            clean_heading = re.sub(r'\s{2,}', ' ', stripped)
            html_parts.append(f'<h2>{clean_heading}</h2>')
        else:
            buffer.append(stripped)

    flush_buffer()

    # Assembler le HTML final (format compatible ebooklib / lxml)
    body = '\n'.join(html_parts)
    return (
        "<html><head>"
        f"<meta charset='utf-8'/><title>{title}</title>"
        "<style>"
        "body{font-family:Georgia,serif;line-height:1.75;padding:1.5rem 2rem;color:#1C1C28;background:#FFFDF7}"
        "h1{font-size:1.6rem;margin-bottom:1.5rem;line-height:1.2;color:#07122a}"
        "h2{font-size:1.2rem;margin:1.8em 0 .6em;color:#07122a;border-bottom:1px solid rgba(0,0,0,.1);padding-bottom:.3em}"
        "p{margin-bottom:1em;text-align:justify}"
        "</style></head><body>"
        f"<h1>{title}</h1>"
        f"{body}"
        "</body></html>"
    )


def pdf_to_epub(article: dict) -> str:
    """Télécharge le PDF, extrait le texte, génère un EPUB."""
    art_id = article["id"]
    title = article["title"]
    lang = article["lang"]
    url = article["pdf"]
    out_path = os.path.join(OUTPUT_DIR, f"{art_id}.epub")

    print(f"  Téléchargement: {title}...")
    resp = requests.get(url, timeout=60, headers=HEADERS)
    if resp.status_code != 200:
        print(f"  ERREUR HTTP {resp.status_code} pour {url}")
        return None

    print(f"  Extraction du texte ({len(resp.content)//1024} Ko)...")
    reader = PyPDF2.PdfReader(io.BytesIO(resp.content))
    raw_pages = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            raw_pages.append(t)

    raw_text = '\n'.join(raw_pages)
    clean = clean_text(raw_text)
    print(f"  Texte nettoyé: {len(clean)} caractères, {len(reader.pages)} pages source")

    # Créer l'EPUB
    book = epub.EpubBook()
    book.set_identifier(f"levangile-article-{art_id}")
    book.set_title(title)
    book.set_language(lang)
    book.add_author("L'Évangile du Royaume")

    # Chapitre principal
    html_content = text_to_html_sections(clean, title)
    chapter = epub.EpubHtml(title=title, file_name="content.xhtml", lang=lang)
    chapter.content = html_content
    chapter.media_type = "application/xhtml+xml"
    book.add_item(chapter)

    # Navigation
    book.toc = [epub.Link("content.xhtml", title, "content")]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    epub.write_epub(out_path, book)
    print(f"  Généré: {out_path}")
    return out_path


if __name__ == "__main__":
    print("=== Génération des EPUBs pour les articles ===\n")
    success = []
    errors = []
    for article in ARTICLES:
        print(f"\n[{article['id']}] {article['title']}")
        try:
            path = pdf_to_epub(article)
            if path:
                success.append(article["id"])
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ERREUR: {e}")
            errors.append((article["id"], str(e)))

    print(f"\n=== Résultat ===")
    print(f"Succès: {len(success)} EPUBs générés → {success}")
    if errors:
        print(f"Erreurs: {errors}")
    print(f"\nFichiers dans {OUTPUT_DIR}:")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
        print(f"  {f} ({size//1024} Ko)")
