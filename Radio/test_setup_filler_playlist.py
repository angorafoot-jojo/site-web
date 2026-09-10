"""Tests de la playlist de secours qui comble les résidus de fin de bloc."""

from __future__ import annotations

import pytest

from azuracast_rotation_4_blocs import MediaItem
from setup_filler_playlist import (
    CRITICAL_SETTINGS,
    FILLER_SETTINGS,
    MAX_FILLER_SECONDS,
    MIN_FILLER_SECONDS,
    extra_paths,
    missing_paths,
    settings_drift,
    select_filler_items,
)


def item(path, length, source="bible"):
    return MediaItem(id=abs(hash(path)) % 99999, path=path, title=path,
                     length=length, source=source)


def jingle(path, length=12):
    return item(path, length, source="jingle")


# ── Sélection des titres éligibles ───────────────────────────────────────────

def test_retient_jingles_et_chapitres_courts():
    """Le résidu mesuré va de 1 à 55 s : il faut du court, des deux sources."""
    choisis = select_filler_items(
        [jingle("Jingle/id_station_03.mp3", 12)],
        [item("La bible/psaumes_117.mp3", 16)],
    )
    assert [i.path for i in choisis] == [
        "Jingle/id_station_03.mp3",      # 12 s
        "La bible/psaumes_117.mp3",      # 16 s — tri par durée croissante
    ]


def test_ecarte_les_titres_trop_longs():
    """Un chapitre de 4 min déborderait franchement sur le bloc suivant."""
    choisis = select_filler_items([], [item("La bible/amos_001.mp3", 240)])
    assert choisis == []


def test_ecarte_les_titres_trop_courts():
    """Même plancher que la rotation : sous 9 s l'AutoDJ échoue à lancer."""
    choisis = select_filler_items([jingle("Jingle/trop_court.mp3", 5)], [])
    assert choisis == []


@pytest.mark.parametrize("length,retenu", [
    (MIN_FILLER_SECONDS - 1, False),
    (MIN_FILLER_SECONDS, True),          # bornes incluses
    (MAX_FILLER_SECONDS, True),
    (MAX_FILLER_SECONDS + 1, False),
])
def test_bornes_de_duree_inclusives(length, retenu):
    choisis = select_filler_items([], [item("La bible/x.mp3", length)])
    assert bool(choisis) is retenu


def test_dedoublonne_un_fichier_present_dans_les_deux_pools():
    """Un jingle catalogué aussi en Bible ne doit pas compter deux fois."""
    partage = jingle("Jingle/partage.mp3", 12)
    choisis = select_filler_items([partage], [partage])
    assert len(choisis) == 1


def test_selection_sur_pools_vides():
    assert select_filler_items([], []) == []


# ── Idempotence de l'import ──────────────────────────────────────────────────
# L'import M3U AJOUTE sans écraser : réimporter l'existant créerait des lignes
# en double. On ne peut pas dédoublonner via PUT /file/{id} — cet endpoint
# réordonnerait les blocs (bug du 02/07/2026).

def test_n_importe_que_les_titres_manquants():
    voulus = [jingle("Jingle/a.mp3"), item("La bible/b.mp3", 16)]
    presents = [jingle("Jingle/a.mp3")]
    assert missing_paths(voulus, presents) == ["La bible/b.mp3"]


def test_playlist_deja_conforme_ne_declenche_aucun_import():
    voulus = [jingle("Jingle/a.mp3"), item("La bible/b.mp3", 16)]
    assert missing_paths(voulus, list(voulus)) == []


def test_playlist_vide_importe_tout():
    voulus = [jingle("Jingle/a.mp3"), item("La bible/b.mp3", 16)]
    assert missing_paths(voulus, []) == ["Jingle/a.mp3", "La bible/b.mp3"]


def test_signale_les_titres_hors_criteres_sans_les_retirer():
    """Le retrait passerait par PUT /file/{id} : signalé, jamais automatique."""
    voulus = [jingle("Jingle/a.mp3")]
    presents = [jingle("Jingle/a.mp3"), item("La bible/trop_long.mp3", 240)]
    assert extra_paths(voulus, presents) == ["La bible/trop_long.mp3"]
    assert missing_paths(voulus, presents) == []


# ── Réglages de la playlist ──────────────────────────────────────────────────

def test_playlist_est_en_rotation_generale_sans_creneau():
    """Le cœur du correctif : une playlist PLANIFIÉE préempterait le bloc au
    lieu de le compléter. En rotation générale, elle ne peut jouer que
    lorsqu'aucune playlist planifiée ne fournit de titre — les 4 blocs +
    BLOC_E + 000_TRANSITION couvrant 100 % de la journée, c'est-à-dire
    uniquement dans les résidus de fin de bloc."""
    assert FILLER_SETTINGS["type"] == "default"
    assert "schedule_items" not in FILLER_SETTINGS
    assert FILLER_SETTINGS["is_enabled"] is True


def test_playlist_est_en_aleatoire_et_evite_les_repetitions():
    """Sans ça, le même psaume à chaque frontière, tous les jours."""
    assert FILLER_SETTINGS["order"] == "shuffle"
    assert FILLER_SETTINGS["avoid_duplicates"] is True


def test_playlist_hors_demandes_auditeurs():
    assert FILLER_SETTINGS["include_in_requests"] is False


# ── Contrôle des réglages réellement enregistrés ─────────────────────────────
# POST /playlists ignore certains champs (README §5) et l'UI AzuraCast permet
# de les changer à la main. Si `type` n'était pas `default`, la playlist
# deviendrait planifiée — donc inopérante comme filet — sans aucun signal.

def playlist_conforme(**surcharges):
    base = {k: FILLER_SETTINGS[k] for k in CRITICAL_SETTINGS}
    return {"id": 36, **base, **surcharges}


def test_aucun_ecart_quand_la_playlist_est_conforme():
    assert settings_drift(playlist_conforme()) == []


def test_signale_un_type_devenu_planifie():
    """Le cas qui casserait tout : une playlist planifiée préempte le bloc."""
    ecarts = settings_drift(playlist_conforme(type="scheduled"))
    assert len(ecarts) == 1
    assert "type" in ecarts[0] and "scheduled" in ecarts[0]


def test_signale_une_playlist_desactivee():
    ecarts = settings_drift(playlist_conforme(is_enabled=False))
    assert any("is_enabled" in e for e in ecarts)


def test_include_in_automation_n_est_pas_controle():
    """L'API ne renvoie pas ce champ pour cette station (dump de
    000_TRANSITION, 10/09/2026) : le contrôler produisait un avertissement
    permanent. Il désigne « Automated Assignment », qui redistribue les
    titres entre playlists — on n'en veut surtout pas ici."""
    assert "include_in_automation" not in CRITICAL_SETTINGS
    assert "include_in_automation" not in FILLER_SETTINGS
    assert settings_drift(playlist_conforme(include_in_automation=None)) == []


@pytest.mark.parametrize("valeur", [True, 1, "true", "1"])
def test_booleens_equivalents_ne_creent_pas_de_faux_ecart(valeur):
    """L'API peut renvoyer 1, True ou 'true' : un avertissement permanent
    n'est pas un avertissement."""
    assert settings_drift(playlist_conforme(is_enabled=valeur)) == []


def test_casse_differente_ne_cree_pas_de_faux_ecart():
    assert settings_drift(playlist_conforme(type="Default")) == []


def test_champ_absent_de_la_reponse_est_signale():
    incomplet = playlist_conforme()
    del incomplet["type"]
    assert any("type" in e for e in settings_drift(incomplet))
