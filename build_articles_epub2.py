#!/usr/bin/env python3
"""
Conversion DOCX/PDF → EPUB pour les articles locaux (articles 8-16).
Lit les fichiers depuis le dossier Downloads puis génère les EPUBs.
"""

import re
import os
import io
import PyPDF2
import docx
from ebooklib import epub

SRC_DIR = "/Users/jonathanangora/Downloads/drive-download-20260528T150939Z-3-001"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "articles")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ARTICLES = [
    {
        "id": 8,
        "title": "Vous devez naître de nouveau",
        "file": "Vous devez naitre de nouveau.pdf",
        "type": "pdf",
        "lang": "fr",
    },
    {
        "id": 9,
        "title": "Vivre le mariage : le modèle de Christ et l'Église",
        "file": "Vivre dans le mariage d_apres le modele de Christ et l_Eglise.docx",
        "type": "docx",
        "lang": "fr",
    },
    {
        "id": 10,
        "title": "Se marier : le modèle de Christ et l'Église",
        "file": "Sur le chemin du mariage d_apres le modele de Christ et l_Eglise.docx",
        "type": "docx",
        "lang": "fr",
    },
    {
        "id": 11,
        "title": "Pourquoi beaucoup de chrétiens sont-ils lents à comprendre ?",
        "file": "Pourquoi beaucoup de chrétiens sont-ils lents à comprendre_.docx",
        "type": "docx",
        "lang": "fr",
    },
    {
        "id": 12,
        "title": "Ayons la justice de Dieu pour être sauvés de la mort",
        "file": "Ayons la justice de Dieu pour être sauvé de la mort.docx",
        "type": "docx",
        "lang": "fr",
    },
    {
        "id": 13,
        "title": "Comment allumer les lampes du chandelier ?",
        "file": "Comment allumer les lampes du chandelier (Exode 40_25).docx",
        "type": "docx",
        "lang": "fr",
    },
    {
        "id": 14,
        "title": "Le mystère de Christ",
        "file": "Le mystère de Christ.docx",
        "type": "docx",
        "lang": "fr",
    },
    {
        "id": 15,
        "title": "Le renoncement aux œuvres mortes : les doctrines fondamentales",
        "file": "Le renoncement aux œuvres mortes_ les doctrines fondamentales.docx",
        "type": "docx",
        "lang": "fr",
    },
    {
        "id": 16,
        "title": "Le Salut",
        "file": "LE SALUT -Alain Angora.docx",
        "type": "docx",
        "lang": "fr",
    },
]


def clean_text(raw: str) -> str:
    """Nettoie le texte extrait d'un PDF ou DOCX."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Corriger les mots fractionnés (ex: "SPIRITUEL LE" → "SPIRITUELLE")
    text = re.sub(r'([A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ])  +([A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ])', r'\1\2', text)

    # Supprimer les numéros de page
    text = re.sub(r'Page\s+\d+\s+sur\s+\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # Supprimer les pieds de page répétitifs
    text = re.sub(r'Email\s*:\s*\S+@\S+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Pour plus d.informations.*$', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"L.équipe de l.Évangile du Royaume", '', text)
    text = re.sub(r"L'ÉVANGILE DU ROYAUM?E?", '', text)
    text = re.sub(r'\[Cet article se veut.*?\]', '', text, flags=re.DOTALL)

    # Réduire les lignes vides multiples
    text = re.sub(r'\n{3,}', '\n\n', text)

    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def extract_from_pdf(path: str) -> str:
    """Extrait le texte d'un fichier PDF."""
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        pages = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                pages.append(t)
    return '\n'.join(pages)


def extract_from_docx(path: str) -> str:
    """Extrait le texte d'un fichier DOCX en préservant la structure."""
    doc = docx.Document(path)
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            lines.append(text)
        else:
            lines.append('')
    return '\n'.join(lines)


def text_to_html_sections(text: str, title: str) -> str:
    """Convertit le texte en HTML structuré."""
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

        letters = [c for c in stripped if c.isalpha()]
        is_heading = False
        if letters:
            ratio = sum(1 for c in letters if c.isupper()) / len(letters)
            if ratio > 0.6 and 5 <= len(stripped) <= 120:
                is_heading = True

        if is_heading:
            flush_buffer()
            clean_heading = re.sub(r'\s{2,}', ' ', stripped)
            html_parts.append(f'<h2>{clean_heading}</h2>')
        else:
            buffer.append(stripped)

    flush_buffer()

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


def build_epub(article: dict) -> str:
    art_id = article["id"]
    title  = article["title"]
    lang   = article["lang"]
    src    = os.path.join(SRC_DIR, article["file"])
    out    = os.path.join(OUTPUT_DIR, f"{art_id}.epub")

    if not os.path.exists(src):
        print(f"  FICHIER INTROUVABLE: {src}")
        return None

    print(f"  Extraction ({article['type'].upper()})...")
    if article["type"] == "pdf":
        raw = extract_from_pdf(src)
    else:
        raw = extract_from_docx(src)

    clean = clean_text(raw)
    print(f"  Texte nettoyé: {len(clean)} caractères")

    book = epub.EpubBook()
    book.set_identifier(f"levangile-article-{art_id}")
    book.set_title(title)
    book.set_language(lang)
    book.add_author("L'Évangile du Royaume")

    html_content = text_to_html_sections(clean, title)
    chapter = epub.EpubHtml(title=title, file_name="content.xhtml", lang=lang)
    chapter.content = html_content
    chapter.media_type = "application/xhtml+xml"
    book.add_item(chapter)

    book.toc = [epub.Link("content.xhtml", title, "content")]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    epub.write_epub(out, book)
    print(f"  Généré: {out}")
    return out


if __name__ == "__main__":
    print("=== Génération des EPUBs (articles 8-16) ===\n")
    success, errors = [], []
    for article in ARTICLES:
        print(f"\n[{article['id']}] {article['title']}")
        try:
            path = build_epub(article)
            if path:
                success.append(article["id"])
        except Exception as e:
            import traceback
            traceback.print_exc()
            errors.append((article["id"], str(e)))

    print(f"\n=== Résultat ===")
    print(f"Succès: {len(success)} EPUBs → {success}")
    if errors:
        print(f"Erreurs: {errors}")
    print(f"\nFichiers dans {OUTPUT_DIR}:")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
        print(f"  {f} ({size//1024} Ko)")
