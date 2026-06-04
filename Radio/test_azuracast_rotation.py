#!/usr/bin/env python3
"""Tests unitaires pour azuracast_rotation_4_blocs.py

Vérifie que chaque jingle est toujours sélectionné dans la bonne catégorie
selon sa position dans le CYCLE_PLAN.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from azuracast_rotation_4_blocs import (
    Episode, MediaItem, CYCLE_PLAN,
    categorize_jingles, pick_jingle_from_category, build_full_cycle,
)


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_jingle(path: str, length: int = 5) -> MediaItem:
    return MediaItem(id=abs(hash(path)) % 100000, path=path, title=path, length=length, source="jingle")

def make_media(prefix: str, n: int, length: int = 300) -> list[MediaItem]:
    return [MediaItem(id=i, path=f"{prefix}_{i}.mp3", title=f"{prefix} {i}", length=length, source=prefix) for i in range(n)]

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

def run_build(jingle_categories=None) -> list[dict]:
    """Lance build_full_cycle et retourne uniquement les blocs de type jingle du debug."""
    cats = jingle_categories or build_test_jingle_categories()
    message = Episode("série_test", "titre_test", "message_test.mp3")
    music = make_media("music", 30)
    bible = make_media("bible", 40, length=200)

    _, debug = build_full_cycle(
        block_name="BLOC_TEST",
        message=message,
        music_files=music,
        bible_files=bible,
        jingle_categories=cats,
        used_music_global=set(),
        used_bible_global=set(),
    )
    return [b for b in debug["blocks"] if b["type"] == "jingle"]


# ─── Tests ──────────────────────────────────────────────────────────────────

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
        jingles = run_build(cats)
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
        jingles = run_build(cats)
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
        jingles = run_build(cats)
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
        jingles = run_build(cats)
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
        jingles = run_build(cats)
        paths = [j["path"] for j in jingles]
        for i in range(len(paths) - 1):
            assert paths[i] != paths[i + 1], \
                f"Run {run}: jingle dupliqué consécutif à la position {i}: {paths[i]}"
    print("✅ test_no_consecutive_duplicate_jingle (10 runs)")


def test_debug_output_contains_category():
    """Le debug de chaque bloc jingle doit contenir le champ 'category'."""
    cats = build_test_jingle_categories()
    jingles = run_build(cats)
    for jb in jingles:
        assert "category" in jb, f"Champ 'category' manquant dans le debug: {jb}"
    print("✅ test_debug_output_contains_category")


# ─── Runner ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_cycle_plan_jingle_count,
        test_cycle_plan_categories_declared,
        test_first_jingle_is_avant_message,
        test_jingles_before_bible_are_avant_bible,
        test_jingles_before_louange_are_avant_louange,
        test_fallback_when_category_empty,
        test_categorize_jingles_splits_correctly,
        test_no_consecutive_duplicate_jingle,
        test_debug_output_contains_category,
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
