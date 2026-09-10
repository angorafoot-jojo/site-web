"""Tests de la normalisation des fondus de jingles."""

from __future__ import annotations

import pytest

from set_jingle_fades import (
    FADES,
    RELIABLE_JINGLE_SECONDS,
    format_media_line,
    is_jingle,
    needs_fade_reset,
    select_jingles_to_fix,
)


def make_media(path="Jingle/j.mp3", length=10, fade_in=0, fade_out=0, fade_overlap=0, **extra):
    return {
        "id": 1, "path": path, "length": length,
        "fade_in": fade_in, "fade_out": fade_out, "fade_overlap": fade_overlap,
        **extra,
    }


# ── is_jingle ────────────────────────────────────────────────────────────────

def test_is_jingle_reconnait_le_dossier_jingle():
    assert is_jingle(make_media(path="Jingle/jingle_avant_bible_08.mp3"))


@pytest.mark.parametrize("path", [
    "La bible/amos_001.mp3",
    "Parole qui éclaire/pqe_j7.mp3",
    "Musique/cantique.mp3",
    "jingle_a_la_racine.mp3",          # hors dossier : ne doit pas être touché
])
def test_is_jingle_ignore_le_reste_de_la_mediatheque(path):
    assert not is_jingle(make_media(path=path))


def test_is_jingle_tolere_un_champ_path_absent():
    assert not is_jingle({})


# ── needs_fade_reset ─────────────────────────────────────────────────────────

def test_fondus_deja_a_zero_ne_sont_pas_retouches():
    assert not needs_fade_reset(make_media())


def test_fondus_a_zero_en_flottant_sont_conformes():
    """Idempotence : l'API renvoie 0.0 après un PUT, pas 0."""
    assert not needs_fade_reset(make_media(fade_in=0.0, fade_out=0.0, fade_overlap=0.0))


def test_champ_null_est_a_corriger():
    """`None` = « hériter du crossfade station » : c'est LE cas à corriger."""
    assert needs_fade_reset(make_media(fade_in=None))


def test_champ_manquant_est_a_corriger():
    media = make_media()
    del media["fade_overlap"]
    assert needs_fade_reset(media)


@pytest.mark.parametrize("champ", ["fade_in", "fade_out", "fade_overlap"])
def test_un_seul_fondu_non_nul_suffit(champ):
    assert needs_fade_reset(make_media(**{champ: 2}))


# ── select_jingles_to_fix ────────────────────────────────────────────────────

def test_selection_ne_retient_que_les_jingles_non_conformes():
    files = [
        make_media(path="Jingle/conforme.mp3"),
        make_media(path="Jingle/a_corriger.mp3", fade_in=2, fade_out=2),
        make_media(path="La bible/amos_001.mp3", fade_in=2),   # hors périmètre
    ]
    jingles, todo = select_jingles_to_fix(files)
    assert len(jingles) == 2
    assert [f["path"] for f in todo] == ["Jingle/a_corriger.mp3"]


def test_selection_sur_mediatheque_vide():
    assert select_jingles_to_fix([]) == ([], [])


def test_pool_entierement_conforme_ne_donne_rien_a_faire():
    files = [make_media(path=f"Jingle/j{i}.mp3") for i in range(5)]
    _, todo = select_jingles_to_fix(files)
    assert todo == []


# ── format_media_line ────────────────────────────────────────────────────────

def test_ligne_signale_un_jingle_devenu_indiffusable():
    """9 s avec 2 s de fondu de chaque côté → 5 s utiles, sous le seuil."""
    ligne = format_media_line(make_media(length=9, fade_in=2, fade_out=2))
    assert "5s utiles" in ligne
    assert "indiffusable" in ligne


def test_ligne_ne_signale_rien_quand_la_duree_utile_est_suffisante():
    ligne = format_media_line(make_media(length=13, fade_in=2, fade_out=2))
    assert "9s utiles" in ligne
    assert "indiffusable" not in ligne


def test_duree_utile_ne_devient_jamais_negative():
    ligne = format_media_line(make_media(length=1, fade_in=2, fade_out=2))
    assert "0s utiles" in ligne


def test_seuil_fiable_documente():
    """Le seuil sert de garde-fou : le figer évite une dérive silencieuse."""
    assert RELIABLE_JINGLE_SECONDS == 9
    assert set(FADES) == {"fade_in", "fade_out", "fade_overlap"}
