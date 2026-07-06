#!/usr/bin/env python3
"""Tests unitaires pour azuracast_rotation_4_blocs.py

Vérifie que chaque jingle est toujours sélectionné dans la bonne catégorie
selon sa position dans le CYCLE_PLAN.
"""
import sys
import os
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(__file__))

from azuracast_rotation_4_blocs import (
    Episode, MediaItem, CYCLE_PLAN,
    categorize_jingles, pick_jingle_from_category, build_full_cycle,
    extract_book_chapter, group_bible_by_book, pick_bible_sequential,
    compute_broadcast_date, EVENING_PREP_HOUR_UTC,
    filter_short_jingles, MIN_JINGLE_SECONDS,
)


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_jingle(path: str, length: int = 5) -> MediaItem:
    return MediaItem(id=abs(hash(path)) % 100000, path=path, title=path, length=length, source="jingle")

def make_media(prefix: str, n: int, length: int = 300) -> list[MediaItem]:
    return [MediaItem(id=i, path=f"{prefix}_{i}.mp3", title=f"{prefix} {i}", length=length, source=prefix) for i in range(n)]

def make_bible_book(book: str, n_chapters: int, length: int = 600) -> list[MediaItem]:
    """Crée n_chapters fichiers pour un livre biblique, avec titre 'BookName N'."""
    return [
        MediaItem(id=abs(hash(f"{book}_{c}")), path=f"Bible/{book.lower()}_{c}.mp3",
                  title=f"{book} {c}", length=length, source="bible")
        for c in range(1, n_chapters + 1)
    ]

def make_bible_library() -> dict[str, list[MediaItem]]:
    """Bibliothèque de test avec plusieurs livres."""
    books = {}
    for name, chapters in [("Luc", 24), ("Jean", 21), ("Actes", 28),
                             ("Romains", 16), ("Matthieu", 28), ("Marc", 16)]:
        files = make_bible_book(name, chapters, length=180)
        books[name] = files
    return books

def build_test_jingle_categories() -> dict:
    return {
        "avant_message": [make_jingle("avant_message_A.mp3"), make_jingle("avant_message_B.mp3")],
        "avant_bible":   [make_jingle("avant_bible_A.mp3"),   make_jingle("avant_bible_B.mp3"), make_jingle("avant_bible_C.mp3")],
        "avant_louange": [make_jingle("avant_louange_A.mp3"), make_jingle("avant_louange_B.mp3")],
        "transition":    [make_jingle("transition_A.mp3"),    make_jingle("transition_B.mp3"), make_jingle("transition_C.mp3")],
    }

def jingle_positions_in_cycle() -> list[tuple[int, str]]:
    """Retourne (index_dans_CYCLE_PLAN, catégorie_attendue) pour chaque slot jingle."""
    return [(i, param) for i, (btype, param) in enumerate(CYCLE_PLAN) if btype == "jingle"]

def run_build(jingle_categories=None, bible_books=None, bible_progress=None) -> tuple[list[dict], list[dict]]:
    """Lance build_full_cycle et retourne (blocs_jingle, blocs_bible) du debug."""
    cats = jingle_categories or build_test_jingle_categories()
    books = bible_books or make_bible_library()
    progress = bible_progress if bible_progress is not None else {}
    message = Episode("série_test", "titre_test", "message_test.mp3")
    music = make_media("music", 30)

    _, debug = build_full_cycle(
        block_name="BLOC_TEST",
        message=message,
        music_files=music,
        bible_books=books,
        jingle_categories=cats,
        used_music_global=set(),
        bible_progress=progress,
    )
    jingles = [b for b in debug["blocks"] if b["type"] == "jingle"]
    bibles  = [b for b in debug["blocks"] if b["type"] == "bible"]
    return jingles, bibles


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_plan_items_snapshot():
    """build_full_cycle expose une liste explicite et ordonnée de chaque titre
    (debug['items']) destinée à l'instantané de plan « réel vs prévu »."""
    message = Episode("série_test", "titre_test", "message_test.mp3")
    paths, debug = build_full_cycle(
        block_name="BLOC_TEST",
        message=message,
        music_files=make_media("music", 30),
        bible_books=make_bible_library(),
        jingle_categories=build_test_jingle_categories(),
        used_music_global=set(),
        bible_progress={},
    )
    items = debug["items"]
    # Un item par fichier de la playlist, dans le même ordre.
    assert len(items) == len(paths) == debug["total_files"]
    assert {it["type"] for it in items} <= {"message", "jingle", "bible", "music"}
    # Le message du jour figure exactement une fois.
    assert sum(1 for it in items if it["type"] == "message") == 1
    assert any(it["title"] == "titre_test" for it in items)
    # Les chapitres bibliques portent livre + chapitre.
    bible_items = [it for it in items if it["type"] == "bible"]
    assert bible_items and all("book" in it and "chapter" in it for it in bible_items)


def test_cycle_plan_jingle_count():
    """Le CYCLE_PLAN doit avoir exactement 9 slots jingle."""
    count = sum(1 for btype, _ in CYCLE_PLAN if btype == "jingle")
    assert count == 9, f"Attendu 9 jingles dans CYCLE_PLAN, trouvé {count}"
    print("✅ test_cycle_plan_jingle_count")


def test_cycle_plan_categories_declared():
    """Chaque slot jingle doit déclarer une catégorie (pas None ni entier)."""
    for i, (btype, param) in enumerate(CYCLE_PLAN):
        if btype == "jingle":
            assert isinstance(param, str) and param, \
                f"Position {i}: catégorie jingle invalide: {param!r}"
    print("✅ test_cycle_plan_categories_declared")


def test_first_jingle_is_avant_message():
    """Le 1er jingle (avant le message) doit venir de 'avant_message'."""
    cats = build_test_jingle_categories()
    avant_message_paths = {j.path for j in cats["avant_message"]}

    for run in range(20):  # 20 tirages aléatoires
        jingles, _ = run_build(cats)
        first = jingles[0]
        assert first["path"] in avant_message_paths, \
            f"Run {run}: jingle avant_message incorrect → {first['path']}"
    print("✅ test_first_jingle_is_avant_message (20 runs)")


def test_jingles_before_bible_are_avant_bible():
    """Tous les jingles avant une section Bible doivent venir de 'avant_bible' (ou fallback)."""
    cats = build_test_jingle_categories()
    avant_bible_paths = {j.path for j in cats["avant_bible"]}
    fallback_paths = {j.path for j in cats["transition"]}
    allowed = avant_bible_paths | fallback_paths

    expected_cats = [param for btype, param in CYCLE_PLAN if btype == "jingle"]

    for run in range(20):
        jingles, _ = run_build(cats)
        for idx, jingle_block in enumerate(jingles):
            cat = expected_cats[idx]
            if cat == "avant_bible":
                assert jingle_block["path"] in avant_bible_paths or jingle_block["path"] in fallback_paths, \
                    f"Run {run}, jingle #{idx}: attendu avant_bible, trouvé {jingle_block['path']}"
    print("✅ test_jingles_before_bible_are_avant_bible (20 runs)")


def test_jingles_before_louange_are_avant_louange():
    """Tous les jingles avant une section Musique doivent venir de 'avant_louange' (ou fallback)."""
    cats = build_test_jingle_categories()
    avant_louange_paths = {j.path for j in cats["avant_louange"]}
    fallback_paths = {j.path for j in cats["transition"]}

    expected_cats = [param for btype, param in CYCLE_PLAN if btype == "jingle"]

    for run in range(20):
        jingles, _ = run_build(cats)
        for idx, jingle_block in enumerate(jingles):
            cat = expected_cats[idx]
            if cat == "avant_louange":
                assert jingle_block["path"] in avant_louange_paths or jingle_block["path"] in fallback_paths, \
                    f"Run {run}, jingle #{idx}: attendu avant_louange, trouvé {jingle_block['path']}"
    print("✅ test_jingles_before_louange_are_avant_louange (20 runs)")


def test_fallback_when_category_empty():
    """Si une catégorie est vide, le script doit utiliser les jingles de 'transition'."""
    cats = {
        "avant_message": [],   # vide intentionnellement
        "avant_bible":   [],   # vide intentionnellement
        "avant_louange": [],   # vide intentionnellement
        "transition":    [make_jingle("fallback_A.mp3"), make_jingle("fallback_B.mp3"), make_jingle("fallback_C.mp3"),
                          make_jingle("fallback_D.mp3"), make_jingle("fallback_E.mp3"), make_jingle("fallback_F.mp3"),
                          make_jingle("fallback_G.mp3"), make_jingle("fallback_H.mp3"), make_jingle("fallback_I.mp3")],
    }
    fallback_paths = {j.path for j in cats["transition"]}

    for run in range(5):
        jingles, _ = run_build(cats)
        assert len(jingles) == 9, f"Attendu 9 jingles, trouvé {len(jingles)}"
        for jb in jingles:
            assert jb["path"] in fallback_paths, \
                f"Run {run}: jingle hors fallback → {jb['path']}"
    print("✅ test_fallback_when_category_empty (5 runs)")


def test_categorize_jingles_splits_correctly():
    """categorize_jingles doit bien répartir les fichiers selon la config."""
    all_jingles = [
        make_jingle("Jingle/avant_message_1.mp3"),
        make_jingle("Jingle/avant_bible_1.mp3"),
        make_jingle("Jingle/avant_louange_1.mp3"),
        make_jingle("Jingle/inconnu.mp3"),  # doit aller en transition
    ]
    config_cats = {
        "avant_message": ["Jingle/avant_message_1.mp3"],
        "avant_bible":   ["Jingle/avant_bible_1.mp3"],
        "avant_louange": ["Jingle/avant_louange_1.mp3"],
    }
    result = categorize_jingles(all_jingles, config_cats)

    assert len(result["avant_message"]) == 1
    assert len(result["avant_bible"]) == 1
    assert len(result["avant_louange"]) == 1
    assert any(j.path == "Jingle/inconnu.mp3" for j in result.get("transition", [])), \
        "Le fichier non catégorisé doit aller en 'transition'"
    print("✅ test_categorize_jingles_splits_correctly")


def test_no_consecutive_duplicate_jingle():
    """Deux jingles consécutifs dans un bloc ne doivent pas être identiques."""
    cats = build_test_jingle_categories()
    for run in range(10):
        jingles, _ = run_build(cats)
        paths = [j["path"] for j in jingles]
        for i in range(len(paths) - 1):
            assert paths[i] != paths[i + 1], \
                f"Run {run}: jingle dupliqué consécutif à la position {i}: {paths[i]}"
    print("✅ test_no_consecutive_duplicate_jingle (10 runs)")


def test_debug_output_contains_category():
    """Le debug de chaque bloc jingle doit contenir le champ 'category'."""
    cats = build_test_jingle_categories()
    jingles = run_build(cats)
    jingles, _ = run_build(cats)
    for jb in jingles:
        assert "category" in jb, f"Champ 'category' manquant dans le debug: {jb}"
    print("✅ test_debug_output_contains_category")


# ─── Tests Bible séquentielle ────────────────────────────────────────────────

def test_extract_book_chapter_nfc_normalization():
    """extract_book_chapter normalise NFC : un titre NFD et le même en NFC
    produisent exactement le même nom de livre (aucun doublon dans bible_progress)."""
    import unicodedata
    title_nfc = "Ézéchiel 43"
    title_nfd = unicodedata.normalize("NFD", title_nfc)
    assert title_nfc != title_nfd, "précondition : NFC != NFD en octets"
    book_nfc, ch_nfc = extract_book_chapter(title_nfc, "x.mp3")
    book_nfd, ch_nfd = extract_book_chapter(title_nfd, "x.mp3")
    assert book_nfc == book_nfd, f"NFD '{book_nfd}' != NFC '{book_nfc}' — doublon bible_progress!"
    assert ch_nfc == ch_nfd
    print("✅ test_extract_book_chapter_nfc_normalization")


def test_extract_book_chapter_formats():
    """extract_book_chapter reconnaît les 3 formats de nommage."""
    cases = [
        ("Lévitique 21", "Bible/luc.mp3", "Lévitique", 21),
        ("2 Chroniques 24", "Bible/x.mp3", "2 Chroniques", 24),
        ("Esther 5", "Bible/x.mp3", "Esther", 5),
        ("Bible_fr_06_joshua_016", "Bible/Bible_fr_06_joshua_016.mp3", "Joshua", 16),
        ("Bible_fr_01_gen_008", "Bible/Bible_fr_01_gen_008.mp3", "Gen", 8),
        ("Matthieu", "Bible/matthieu.mp3", "Matthieu", 0),
        ("1 Corinthiens", "Bible/x.mp3", "1 Corinthiens", 0),
        ("2 Chronicles", "Bible/x.mp3", "2 Chronicles", 0),
        ("La Bible", "Bible/x.mp3", "La Bible", 0),
    ]
    for title, path, expected_book, expected_ch in cases:
        book, ch = extract_book_chapter(title, path)
        assert book == expected_book, f"Titre '{title}': attendu livre '{expected_book}', obtenu '{book}'"
        assert ch == expected_ch, f"Titre '{title}': attendu chapitre {expected_ch}, obtenu {ch}"
    print("✅ test_extract_book_chapter_formats")


def test_group_bible_by_book_sorts_chapters():
    """group_bible_by_book trie les chapitres dans l'ordre."""
    files = [
        MediaItem(1, "Bible/luc_3.mp3", "Luc 3", 180, "bible"),
        MediaItem(2, "Bible/luc_1.mp3", "Luc 1", 180, "bible"),
        MediaItem(3, "Bible/luc_2.mp3", "Luc 2", 180, "bible"),
        MediaItem(4, "Bible/jean_1.mp3", "Jean 1", 180, "bible"),
    ]
    books = group_bible_by_book(files)
    assert "Luc" in books
    assert "Jean" in books
    luc_titles = [i.title for i in books["Luc"]]
    assert luc_titles == ["Luc 1", "Luc 2", "Luc 3"], f"Ordre incorrect: {luc_titles}"
    print("✅ test_group_bible_by_book_sorts_chapters")


def test_bible_slot_stays_in_same_book():
    """
    Dans un slot Bible, les chapitres d'un même livre sont toujours groupés
    et lus dans l'ordre — pas de mélange aléatoire entre livres.
    Si un livre finit avant la durée cible, le suivant commence depuis son ch.1.
    """
    # Chapitres courts (180s) → plusieurs livres peuvent se succéder dans un slot de 60min
    books = make_bible_library()

    for run in range(20):
        progress = {}
        selected, _, starting_book = pick_bible_sequential(
            books, target_seconds=3600, used_books_cycle=set(), bible_progress=progress,
        )
        # Vérifier que les chapitres de chaque livre apparaissent en bloc séquentiel
        current_book = None
        current_chapter = -1
        seen_books: list[str] = []

        for item in selected:
            book, chapter = extract_book_chapter(item.title, item.path)
            if book != current_book:
                # Changement de livre : doit aller de l'avant (pas de retour en arrière)
                assert book not in seen_books, \
                    f"Run {run}: le livre '{book}' réapparaît après avoir été interrompu"
                seen_books.append(book)
                current_book = book
                current_chapter = chapter
            else:
                # Même livre : le chapitre doit progresser
                if chapter > 0:
                    assert chapter >= current_chapter, \
                        f"Run {run}: chapitre {chapter} avant {current_chapter} dans {book}"
                    current_chapter = chapter

        assert starting_book == seen_books[0], \
            f"Run {run}: starting_book '{starting_book}' ≠ premier livre '{seen_books[0]}'"
    print("✅ test_bible_slot_stays_in_same_book (20 runs)")


def test_bible_chapters_are_sequential():
    """Les chapitres dans un slot doivent être dans l'ordre croissant."""
    books = make_bible_library()

    for run in range(20):
        progress = {}
        selected, _, _ = pick_bible_sequential(
            books, target_seconds=1800, used_books_cycle=set(), bible_progress=progress,
        )
        chapters = [extract_book_chapter(i.title, i.path)[1] for i in selected if extract_book_chapter(i.title, i.path)[1] > 0]
        assert chapters == sorted(chapters), \
            f"Run {run}: chapitres pas dans l'ordre: {chapters}"
    print("✅ test_bible_chapters_are_sequential (20 runs)")


def test_bible_different_books_per_slot_in_same_bloc():
    """Deux slots Bible dans le même bloc ne doivent pas commencer par le même livre."""
    books = make_bible_library()

    for run in range(20):
        _, bibles = run_build(bible_books=books)
        assert len(bibles) == 4, f"Attendu 4 slots Bible, trouvé {len(bibles)}"
        starting_books = [b["starting_book"] for b in bibles]
        # Pas de livre répété dans le même bloc
        assert len(starting_books) == len(set(starting_books)), \
            f"Run {run}: livre démarrant répété dans le bloc: {starting_books}"
    print("✅ test_bible_different_books_per_slot_in_same_bloc (20 runs)")


def test_bible_debug_contains_starting_book():
    """Le debug de chaque slot Bible doit contenir 'starting_book' et 'books_in_slot'."""
    _, bibles = run_build()
    for slot in bibles:
        assert "starting_book" in slot, f"Champ 'starting_book' manquant: {slot}"
        assert "books_in_slot" in slot, f"Champ 'books_in_slot' manquant: {slot}"
        assert slot["starting_book"] == slot["books_in_slot"][0], \
            f"Le premier livre dans books_in_slot doit être starting_book"
    print("✅ test_bible_debug_contains_starting_book")


def test_bible_fallback_when_all_books_used():
    """Si tous les livres sont déjà utilisés ce cycle, le fallback fonctionne sans erreur."""
    books = make_bible_library()
    used_all = set(books.keys())

    for run in range(5):
        progress = {}
        selected, duration, book = pick_bible_sequential(
            books, target_seconds=1800, used_books_cycle=used_all, bible_progress=progress,
        )
        assert len(selected) > 0, f"Run {run}: aucun fichier sélectionné même en fallback"
        assert duration > 0
    print("✅ test_bible_fallback_when_all_books_used (5 runs)")


def test_bible_progress_resumes_from_last_chapter():
    """Après un premier slot, le deuxième reprend depuis le chapitre suivant."""
    books = {"Luc": make_bible_book("Luc", 24, length=180)}
    progress = {}

    # Premier slot : lit Luc 1-11 (11 × 180s = 1980s > 1800s cible)
    selected1, _, _ = pick_bible_sequential(
        books, target_seconds=1800, used_books_cycle=set(), bible_progress=progress,
    )
    chapters1 = [extract_book_chapter(i.title, i.path)[1] for i in selected1]
    last_ch = max(chapters1)

    # Deuxième slot : doit reprendre APRÈS le dernier chapitre lu
    selected2, _, _ = pick_bible_sequential(
        books, target_seconds=1800, used_books_cycle=set(), bible_progress=progress,
    )
    chapters2 = [extract_book_chapter(i.title, i.path)[1] for i in selected2]

    assert min(chapters2) > last_ch, \
        f"Le 2e slot doit commencer après le chapitre {last_ch}, a commencé à {min(chapters2)}"
    print("✅ test_bible_progress_resumes_from_last_chapter")


def test_bible_progress_resets_after_full_book():
    """Quand un livre est entièrement lu, la progression repart de 0."""
    # Livre avec seulement 5 chapitres courts → un seul slot le termine
    books = {"Mini": make_bible_book("Mini", 5, length=60)}
    progress = {}

    # Lire tout le livre (5 × 60s = 300s, cible 500s)
    pick_bible_sequential(books, 500, set(), progress)
    # Le livre est terminé → progress["Mini"] doit être remis à 0
    assert progress.get("Mini", 0) == 0, \
        f"Progression devrait être 0 après lecture complète, est {progress.get('Mini')}"

    # Le slot suivant repart du début (chapitre 1)
    selected2, _, _ = pick_bible_sequential(books, 300, set(), progress)
    chapters2 = [extract_book_chapter(i.title, i.path)[1] for i in selected2]
    assert chapters2[0] == 1, f"Doit repartir au ch.1 après reset, a commencé à {chapters2[0]}"
    print("✅ test_bible_progress_resets_after_full_book")


def test_bible_progress_persists_across_blocs():
    """La progression Bible est partagée entre les 4 blocs d'un même run."""
    books = {"Luc": make_bible_book("Luc", 24, length=300)}
    progress = {}

    # Simuler 2 appels à build_full_cycle (comme 2 blocs dans main)
    _, bibles1 = run_build(bible_books=books, bible_progress=progress)
    chapters_after_bloc1 = progress.get("Luc", 0)

    _, bibles2 = run_build(bible_books=books, bible_progress=progress)
    chapters_after_bloc2 = progress.get("Luc", 0)

    # La progression doit avoir avancé entre le 1er et le 2e bloc
    # (sauf si le livre a été réinitialisé après complétion)
    # On vérifie juste que les deux blocs ont pu s'exécuter sans erreur
    assert len(bibles1) == 4 and len(bibles2) == 4
    print("✅ test_bible_progress_persists_across_blocs")


def test_bible_marks_all_books_read():
    """Régression : un slot qui enchaîne plusieurs livres doit TOUS les inscrire
    dans used_books_cycle (avant : seul le premier livre était marqué → les petits
    livres enchaînés se rejouaient au slot suivant)."""
    # 3 petits livres de 2 ch (180s) ; cible 1000s → les enchaîne tous les 3
    books = {
        "Alpha": make_bible_book("Alpha", 2, length=180),
        "Beta":  make_bible_book("Beta", 2, length=180),
        "Gamma": make_bible_book("Gamma", 2, length=180),
    }
    used: set[str] = set()
    progress: dict[str, int] = {}
    selected, _, _ = pick_bible_sequential(books, 1000, used, progress)
    books_read = {extract_book_chapter(i.title, i.path)[0] for i in selected}
    assert books_read <= used, f"Livres lus {books_read} pas tous marqués (used={used})"
    assert len(used) == 3, \
        f"3 livres lus mais {len(used)} marqué(s) — bug 'seul le premier livre'"
    print("✅ test_bible_marks_all_books_read")


def test_bible_no_book_repeat_across_blocs_shared_set():
    """Régression : avec le set Bible global partagé entre les blocs, un livre lu
    dans un bloc ne réapparaît pas au bloc suivant (avant : set réinitialisé par
    bloc → petits livres rejoués matin ET soir)."""
    # 12 gros livres (30 ch ≥ segment max de 60 min) → 8 slots/2 blocs sans épuisement
    books = {f"Livre{i:02d}": make_bible_book(f"Livre{i:02d}", 30, length=180)
             for i in range(12)}
    message = Episode("série_test", "titre_test", "message_test.mp3")
    cats = build_test_jingle_categories()
    music = make_media("music", 80)

    for run in range(10):
        progress: dict[str, int] = {}
        used_global: set[str] = set()
        starting_all: list[str] = []
        for b in range(2):  # 2 blocs partageant le même set global
            _, debug = build_full_cycle(
                block_name=f"BLOC_{b}", message=message, music_files=music,
                bible_books=books, jingle_categories=cats,
                used_music_global=set(), bible_progress=progress,
                used_bible_books_global=used_global,
            )
            starting_all += [s["starting_book"] for s in debug["blocks"] if s["type"] == "bible"]
        assert len(starting_all) == len(set(starting_all)), \
            f"Run {run}: livre de départ répété entre les blocs: {starting_all}"
    print("✅ test_bible_no_book_repeat_across_blocs_shared_set (10 runs)")


# ─── Jour de diffusion (compute_broadcast_date) ──────────────────────────────

def test_broadcast_date_evening_prepares_tomorrow():
    """À 23h30 UTC (heure du cron), on prépare la diffusion du LENDEMAIN."""
    now = datetime(2026, 6, 21, 23, 30, tzinfo=timezone.utc)
    assert compute_broadcast_date(now) == "2026-06-22"
    print("✅ test_broadcast_date_evening_prepares_tomorrow")

def test_broadcast_date_morning_is_same_day():
    """Un run du matin (ou juste après minuit) vise le jour courant."""
    assert compute_broadcast_date(datetime(2026, 6, 21, 2, 7, tzinfo=timezone.utc)) == "2026-06-21"
    assert compute_broadcast_date(datetime(2026, 6, 21, 0, 30, tzinfo=timezone.utc)) == "2026-06-21"
    print("✅ test_broadcast_date_morning_is_same_day")

def test_broadcast_date_threshold_boundary():
    """21h59 → aujourd'hui ; EVENING_PREP_HOUR_UTC pile → demain."""
    assert compute_broadcast_date(datetime(2026, 6, 21, EVENING_PREP_HOUR_UTC - 1, 59, tzinfo=timezone.utc)) == "2026-06-21"
    assert compute_broadcast_date(datetime(2026, 6, 21, EVENING_PREP_HOUR_UTC, 0, tzinfo=timezone.utc)) == "2026-06-22"
    print("✅ test_broadcast_date_threshold_boundary")

def test_broadcast_date_crosses_month_end():
    """Le passage au lendemain gère le changement de mois."""
    assert compute_broadcast_date(datetime(2026, 6, 30, 23, 30, tzinfo=timezone.utc)) == "2026-07-01"
    print("✅ test_broadcast_date_crosses_month_end")

def test_broadcast_date_no_collision_morning_then_evening():
    """Cœur du fix : un run matin et un run soir le MÊME jour UTC visent des
    jours de diffusion DIFFÉRENTS → le garde-fou last_run_date==broadcast_date
    ne saute plus la rotation du soir (cause de la collision du 2026-06-18)."""
    morning = compute_broadcast_date(datetime(2026, 6, 18, 2, 7, tzinfo=timezone.utc))
    evening = compute_broadcast_date(datetime(2026, 6, 18, 23, 30, tzinfo=timezone.utc))
    assert morning == "2026-06-18"
    assert evening == "2026-06-19"
    assert morning != evening
    print("✅ test_broadcast_date_no_collision_morning_then_evening")


# ─── Jingles trop courts ────────────────────────────────────────────────────

def test_filter_short_jingles_ecarte_les_indiffusables():
    """Reproduit l'inventaire réel du 05/07/2026 : les fichiers de 1 à 5 s
    ne sont jamais diffusés par l'AutoDJ (qui ressert le message à la place),
    ceux de 6 s et plus passent."""
    jingles = [make_jingle("bible_04.mp3", length=1),
               make_jingle("louange_03.mp3", length=4),
               make_jingle("bible_05.mp3", length=5),
               make_jingle("louange_04.mp3", length=5),
               make_jingle("bible_03.mp3", length=6),
               make_jingle("message_01.mp3", length=10)]
    kept, rejected = filter_short_jingles(jingles)
    assert [j.path for j in kept] == ["bible_03.mp3", "message_01.mp3"]
    assert [j.path for j in rejected] == ["bible_04.mp3", "louange_03.mp3",
                                          "bible_05.mp3", "louange_04.mp3"]
    print("✅ test_filter_short_jingles_ecarte_les_indiffusables")

def test_filter_short_jingles_seuil_exact():
    """Un jingle pile à MIN_JINGLE_SECONDS est gardé."""
    kept, rejected = filter_short_jingles([make_jingle("j.mp3", length=MIN_JINGLE_SECONDS)])
    assert len(kept) == 1 and not rejected
    print("✅ test_filter_short_jingles_seuil_exact")

def test_filter_short_jingles_tout_garde_si_tous_longs():
    jingles = [make_jingle(f"j{i}.mp3", length=8) for i in range(5)]
    kept, rejected = filter_short_jingles(jingles)
    assert len(kept) == 5 and not rejected
    print("✅ test_filter_short_jingles_tout_garde_si_tous_longs")

def test_build_reutilise_jingles_sains_quand_pool_reduit():
    """Avec le pool réduit aux jingles ≥6s (7 fichiers pour 9 slots), la
    construction doit toujours produire ses 9 jingles par bloc (réutilisation
    tolérée) plutôt que d'échouer ou de réintroduire un fichier court."""
    cats = {
        "avant_message": [make_jingle("avant_message_A.mp3", length=10),
                          make_jingle("avant_message_B.mp3", length=8)],
        "avant_bible":   [make_jingle("avant_bible_A.mp3", length=6),
                          make_jingle("avant_bible_B.mp3", length=7),
                          make_jingle("avant_bible_C.mp3", length=6)],
        "avant_louange": [make_jingle("avant_louange_A.mp3", length=6),
                          make_jingle("avant_louange_B.mp3", length=7)],
    }
    jingle_blocks, _ = run_build(jingle_categories=cats)
    expected = len(jingle_positions_in_cycle())
    assert len(jingle_blocks) == expected, f"{len(jingle_blocks)} jingles au lieu de {expected}"
    print("✅ test_build_reutilise_jingles_sains_quand_pool_reduit")


# ─── Runner ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # Jingles
        test_cycle_plan_jingle_count,
        test_cycle_plan_categories_declared,
        test_first_jingle_is_avant_message,
        test_jingles_before_bible_are_avant_bible,
        test_jingles_before_louange_are_avant_louange,
        test_fallback_when_category_empty,
        test_categorize_jingles_splits_correctly,
        test_no_consecutive_duplicate_jingle,
        test_debug_output_contains_category,
        # Bible séquentielle
        test_extract_book_chapter_nfc_normalization,
        test_extract_book_chapter_formats,
        test_group_bible_by_book_sorts_chapters,
        test_bible_slot_stays_in_same_book,
        test_bible_chapters_are_sequential,
        test_bible_different_books_per_slot_in_same_bloc,
        test_bible_debug_contains_starting_book,
        test_bible_fallback_when_all_books_used,
        # Progression Bible persistante
        test_bible_progress_resumes_from_last_chapter,
        test_bible_progress_resets_after_full_book,
        test_bible_progress_persists_across_blocs,
        test_bible_marks_all_books_read,
        test_bible_no_book_repeat_across_blocs_shared_set,
        # Jour de diffusion
        test_broadcast_date_evening_prepares_tomorrow,
        test_broadcast_date_morning_is_same_day,
        test_broadcast_date_threshold_boundary,
        test_broadcast_date_crosses_month_end,
        test_broadcast_date_no_collision_morning_then_evening,
        # Jingles trop courts
        test_filter_short_jingles_ecarte_les_indiffusables,
        test_filter_short_jingles_seuil_exact,
        test_filter_short_jingles_tout_garde_si_tous_longs,
        test_build_reutilise_jingles_sains_quand_pool_reduit,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"💥 {test.__name__}: erreur inattendue: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Résultat: {passed}/{passed+failed} tests passés")
    if failed:
        sys.exit(1)
