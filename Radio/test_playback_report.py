"""Tests de la section « réel vs prévu » du rapport de diffusion.
Fonctions pures uniquement (aucun appel réseau)."""
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from playback_report import (norm_title, build_plan_section, build_health_section,
                             build_report, _window_bounds)

JOUR = date(2026, 6, 25)


def ts(h, m=0, s=0):
    """Timestamp epoch UTC pour le 2026-06-25 à h:m:s."""
    return int(datetime(2026, 6, 25, h, m, s, tzinfo=timezone.utc).timestamp())


def hist(*titres_heures):
    """Construit un historique factice : (titre, heure) -> entrées AzuraCast."""
    return [{"played_at": ts(h), "song": {"title": t}} for (t, h) in titres_heures]


def entry(title, h, m=0, s=0, duration=0, playlist="BLOC_A_SERIE_DU_JOUR"):
    """Entrée d'historique complète (durée + playlist) pour les contrôles approfondis."""
    return {"played_at": ts(h, m, s), "duration": duration,
            "playlist": playlist, "song": {"title": title}}


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
    assert _window_bounds("06:00-12:00") == (360, 720)
    assert _window_bounds("18:00-24:00") == (1080, 1440)
    # BLOC_D s'arrête à 23h30 depuis l'ajout de BLOC_E_LOUANGE_NUIT.
    assert _window_bounds("18:00-23:30") == (1080, 1410)


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


def plan_2_blocs():
    """Plan minimal 2 blocs avec message, jingles et bible (types renseignés,
    comme les vrais plan_*.json écrits par la rotation)."""
    return {
        "message": {"title": "PQE J 1", "duration_seconds": 1800},
        "blocks": [
            {"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
             "items": [{"type": "jingle", "title": "jingle avant message 01"},
                       {"type": "message", "title": "PQE J 1"},
                       {"type": "jingle", "title": "jingle avant bible 02"},
                       {"type": "bible", "title": "Amos 1"}]},
            {"block_name": "BLOC_B_SERIE_DU_JOUR", "window": "06:00-12:00",
             "items": [{"type": "jingle", "title": "jingle avant message 01"},
                       {"type": "message", "title": "PQE J 1"},
                       {"type": "bible", "title": "Amos 2"}]},
        ],
    }


def test_message_compte_et_double_rapproche_detecte():
    # 3 diffusions pour 2 prévues, dont 05:30 → 06:01 dos à dos (fin 06:00).
    h = [entry("jingle avant message 01", 0, 1, duration=10),
         entry("pqe j1", 0, 2, duration=1800),
         entry("Amos 1", 0, 32, duration=300),
         entry("pqe j1", 5, 30, duration=1800),
         entry("pqe j1", 6, 1, duration=1800, playlist="BLOC_B_SERIE_DU_JOUR"),
         entry("Amos 2", 6, 31, duration=300, playlist="BLOC_B_SERIE_DU_JOUR")]
    out = build_health_section(h, JOUR, plan_2_blocs())
    assert "3 diffusion(s) pour 2 prévue(s) ❌" in out
    assert out.count("DOUBLE RAPPROCHÉ") == 1
    assert "reboucle d'un bloc" in out


def test_message_nominal_sans_double():
    h = [entry("pqe j1", 0, 2, duration=1800),
         entry("Amos 1", 0, 32, duration=300),
         entry("pqe j1", 6, 0, duration=1800, playlist="BLOC_B_SERIE_DU_JOUR"),
         entry("Amos 2", 6, 30, duration=300, playlist="BLOC_B_SERIE_DU_JOUR")]
    out = build_health_section(h, JOUR, plan_2_blocs())
    assert "2 diffusion(s) pour 2 prévue(s) ✅" in out
    assert "DOUBLE RAPPROCHÉ" not in out


def test_jingles_comptes_par_fenetre():
    # 1 jingle joué sur 2 prévus en A, 0 sur 1 en B → 1/3 global.
    h = [entry("jingle avant message 01", 0, 1, duration=10),
         entry("pqe j1", 0, 2, duration=1800),
         entry("pqe j1", 6, 0, duration=1800, playlist="BLOC_B_SERIE_DU_JOUR")]
    out = build_health_section(h, JOUR, plan_2_blocs())
    assert "JINGLES : 1 joués / 3 prévus (33%) ⚠️" in out
    assert "BLOC_A 1/2" in out
    assert "BLOC_B 0/1" in out


def test_hors_fenetre_titre_exclusif_seulement():
    # Amos 1 (exclusif au bloc A) joué à 07:00 → débordement signalé.
    # Le message (partagé A+B) joué à 07:30 → PAS signalé (étiquette non fiable).
    h = [entry("Amos 1", 7, 0, duration=300),
         entry("pqe j1", 7, 30, duration=1800)]
    out = build_health_section(h, JOUR, plan_2_blocs())
    assert "HORS FENÊTRE : 1 titre(s)" in out
    assert "Amos 1 — prévu dans BLOC_A (00:00-06:00)" in out


def test_hors_fenetre_ignore_hors_de_toute_fenetre_du_plan():
    # Titre exclusif au bloc A joué à 13:00, hors de TOUTE fenêtre du plan
    # (comme les cantiques de BLOC_E_LOUANGE_NUIT à 23h30-minuit) : pas un
    # débordement de bloc, rien à signaler.
    h = [entry("Amos 1", 13, 0, duration=300)]
    out = build_health_section(h, JOUR, plan_2_blocs())
    assert "HORS FENÊTRE : aucun débordement de bloc détecté ✅" in out


def test_bouche_trou_et_couverture():
    # Journée qui démarre à 00:20 (trou initial) par un bouche-trou AzuraCast,
    # et dont le dernier titre finit vers 06:30 (fin découverte).
    h = [entry("AzuraCast is Live!", 0, 20, duration=10, playlist="?"),
         entry("pqe j1", 0, 21, duration=1800),
         entry("Amos 1", 6, 25, duration=300, playlist="?")]
    out = build_health_section(h, JOUR, plan_2_blocs())
    assert "BOUCHE-TROUS : 1 titre(s)" in out
    assert "AzuraCast is Live!" in out
    assert "trou de 20m00s en début de journée" in out
    assert "fin de journée possiblement découverte" in out


def test_couverture_saine():
    h = [entry("pqe j1", 0, 1, duration=1800),
         entry("Amos 2", 23, 55, duration=310, playlist="BLOC_B_SERIE_DU_JOUR")]
    out = build_health_section(h, JOUR, plan_2_blocs())
    assert "BOUCHE-TROUS : aucun ✅" in out
    assert "début de journée" not in out
    assert "possiblement découverte" not in out


def test_health_sans_plan():
    out = build_health_section([], JOUR, None)
    assert "contrôles approfondis impossibles" in out


def test_gravite_des_anomalies():
    # Trou de 30 s (mineure), coupure de 5 min (sérieuse), trou de 20 min (critique).
    h = [entry("a", 0, 0, duration=60), entry("b", 0, 1, 30, duration=60),
         entry("c", 0, 2, 30, duration=600), entry("d", 0, 7, 30, duration=60),
         entry("e", 0, 28, 30, duration=60), entry("f", 0, 29, 30, duration=60)]
    out, problems = build_report(h, JOUR)
    assert problems == 3
    assert "1 mineure(s) <1min · 1 sérieuse(s) 1-10min · 1 critique(s) >10min" in out


def test_bilan_sans_anomalie_sans_gravite():
    h = [entry("a", 0, 0, duration=60), entry("b", 0, 1, duration=60)]
    out, problems = build_report(h, JOUR)
    assert problems == 0
    assert "Gravité" not in out


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
