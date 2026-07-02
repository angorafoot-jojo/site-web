"""Tests de la section « réel vs prévu » du rapport de diffusion.
Fonctions pures uniquement (aucun appel réseau)."""
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from playback_report import norm_title, build_plan_section, _window_bounds


def ts(h, m=0, s=0):
    """Timestamp epoch UTC pour le 2026-06-25 à h:m:s."""
    return int(datetime(2026, 6, 25, h, m, s, tzinfo=timezone.utc).timestamp())


def hist(*titres_heures):
    """Construit un historique factice : (titre, heure) -> entrées AzuraCast."""
    return [{"played_at": ts(h), "song": {"title": t}} for (t, h) in titres_heures]


def test_norm_title_insensible_accents_casse_ponctuation():
    assert norm_title("Galates 1") == norm_title("galates  1")
    assert norm_title("Éphésiens 2") == norm_title("ephesiens 2")
    assert norm_title("My God — Is Good!") == "mygodisgood"


def test_norm_title_espaces_supprimes_pas_reduits():
    # Régression fin juin 2026 : plan « PQE J 1 » vs historique « pqe j1 » —
    # le message était compté sauté + hors plan dans chaque bloc.
    assert norm_title("PQE J 1") == norm_title("pqe j1")


def test_message_pqe_reconnu_dans_la_conformite():
    plan = {"blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"title": "PQE J 1"}, {"title": "Proverbes 1"}]}]}
    h = hist(("pqe j1", 0), ("Proverbes 1", 1))
    out = build_plan_section(h, date(2026, 6, 25), plan)
    assert "conformité 100%" in out


def test_window_bounds():
    assert _window_bounds("06:00-12:00") == (6, 12)
    assert _window_bounds("18:00-24:00") == (18, 24)


def test_plan_section_absent_signale_proprement():
    out = build_plan_section([], date(2026, 6, 25), None)
    assert "Plan non disponible" in out


def test_conformite_parfaite():
    plan = {"blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"title": "Amos 1"}, {"title": "Amos 2"}]}]}
    h = hist(("Amos 1", 1), ("Amos 2", 2))
    out = build_plan_section(h, date(2026, 6, 25), plan)
    assert "conformité 100%" in out
    assert "CONFORMITÉ GLOBALE : 2/2" in out


def test_detecte_titre_saute_et_titre_hors_plan():
    plan = {"blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"title": "jingle avant bible 01"},
                                  {"title": "Amos 1"}, {"title": "Amos 2"}]}]}
    # le jingle est sauté ; un bouche-trou hors plan s'intercale
    h = hist(("Amos 1", 1), ("AzuraCast is Live!", 2), ("Amos 2", 3))
    out = build_plan_section(h, date(2026, 6, 25), plan)
    assert "jingle avant bible 01" in out          # listé comme prévu non joué
    assert "AzuraCast is Live!" in out             # listé comme joué non prévu
    assert "sautés  1" in out
    assert "en trop  1" in out


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
