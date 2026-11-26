"""Tests de la section « réel vs prévu » du rapport de diffusion.
Fonctions pures uniquement (aucun appel réseau)."""
import os
import sys
from datetime import date, datetime, time, timezone

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from playback_report import (norm_title, build_plan_section, build_health_section,
                             build_report, _window_bounds,
                             classify_server_line, parse_server_events,
                             group_incidents, playback_incidents,
                             parse_watch_records, summarize_watch,
                             nearest_incident, build_monitor_section,
                             is_expected_incident, in_window,
                             ROTATION_WINDOW, MIDNIGHT_RESET_WINDOW,
                             window_around, delay_minutes, is_on_time,
                             watch_time, plan_time, evening_rotation_time,
                             _cut_by_midnight_reset,
                             RESET_SCHEDULED, ROTATION_SCHEDULED,
                             PUNCTUALITY_TOLERANCE_MINUTES)

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


def test_fin_de_bloc_non_atteinte_exclue_de_la_conformite():
    # Le plan embarque un surplus au-delà de la fenêtre (marge anti-rebouclage) :
    # les derniers titres jamais atteints ne comptent plus comme « sautés »
    # et ne pénalisent plus la conformité.
    plan = {"blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"title": "Amos 1", "duration_seconds": 10800},
                                  {"title": "Amos 2", "duration_seconds": 10800},
                                  {"title": "Cantique fin 1", "duration_seconds": 600},
                                  {"title": "Cantique fin 2", "duration_seconds": 600}]}]}
    h = hist(("Amos 1", 0), ("Amos 2", 3))
    out = build_plan_section(h, date(2026, 6, 25), plan)
    assert "conformité 100%" in out
    assert "sautés  0" in out
    assert "FIN DE BLOC NON ATTEINTE (2 titres" in out
    assert "Cantique fin 1" in out
    assert "normal" in out
    assert "CONFORMITÉ GLOBALE : 2/2" in out
    # surplus planifié (1200 s) ≈ part non atteinte → pas d'alerte
    assert "excède la marge" not in out


def test_fin_de_bloc_excedant_la_marge_est_signalee():
    # Bloc amputé : la part non atteinte dépasse largement le surplus planifié
    # (plan de 2h20 pour une fenêtre de 6h → surplus nul, 40 min non atteintes).
    plan = {"blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"title": "Amos 1", "duration_seconds": 3600},
                                  {"title": "Amos 2", "duration_seconds": 2400},
                                  {"title": "Amos 3", "duration_seconds": 2400}]}]}
    h = hist(("Amos 1", 0), ("Amos 2", 1))
    out = build_plan_section(h, date(2026, 6, 25), plan)
    assert "FIN DE BLOC NON ATTEINTE (1 titres" in out
    assert "excède la marge" in out


def test_marge_reste_marge_malgre_artefact_de_frontiere():
    # Régression des 09 et 11/07/2026 : un rebouclage + un bouche-trou joués
    # APRÈS le dernier titre atteint transformaient le « delete » final en
    # « replace » — la marge anti-rebouclage entière passait pour « sautée »
    # (8 faux sautés par bloc). Les artefacts restent comptés « en trop ».
    plan = {"blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"title": "Amos 1", "duration_seconds": 10800},
                                  {"title": "Amos 2", "duration_seconds": 10700},
                                  {"title": "Cantique fin 1", "duration_seconds": 600},
                                  {"title": "Cantique fin 2", "duration_seconds": 600}]}]}
    h = [entry("Amos 1", 0, 0, duration=10800),
         entry("Amos 2", 3, 0, duration=10700),
         entry("jingle avant message 02", 5, 58, duration=8),
         entry("AzuraCast is Live!", 5, 59, duration=30, playlist="?")]
    out = build_plan_section(h, JOUR, plan)
    assert "conformité 100%" in out
    assert "sautés  0" in out
    assert "en trop  2" in out
    assert "FIN DE BLOC NON ATTEINTE (2 titres" in out
    assert "Cantique fin 1" in out


def test_saut_en_milieu_de_bloc_reste_compte():
    # Un titre manquant au milieu (échec AutoDJ) reste un vrai « sauté »,
    # même si la fin du bloc est aussi tronquée.
    plan = {"blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"title": "Amos 1"}, {"title": "jingle avant bible 01"},
                                  {"title": "Amos 2"}, {"title": "Cantique fin"}]}]}
    h = hist(("Amos 1", 0), ("Amos 2", 2))
    out = build_plan_section(h, date(2026, 6, 25), plan)
    assert "sautés  1" in out
    assert "jingle avant bible 01" in out
    assert "FIN DE BLOC NON ATTEINTE (1 titres" in out


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


def test_message_reconnu_par_duree_malgre_tag_fichier_different():
    # Régression 09-11/07/2026 : le plan porte l'étiquette d'épisode de la
    # config (« Tian Le pardon 1 ») mais l'historique journalise le tag du
    # fichier (« La pardon ») → 0 diffusion comptée et détecteur de doubles
    # aveugle. La durée (même média AzuraCast des deux côtés) doit suffire.
    plan = plan_2_blocs()
    plan["message"] = {"title": "Tian Le pardon 1", "duration_seconds": 614}
    for b in plan["blocks"]:
        for it in b["items"]:
            if it["type"] == "message":
                it["title"] = "Tian Le pardon 1"
    h = [entry("La pardon", 0, 2, duration=614),
         entry("Amos 1", 0, 32, duration=300),
         entry("La pardon", 6, 0, duration=614, playlist="BLOC_B_SERIE_DU_JOUR")]
    out = build_health_section(h, JOUR, plan)
    assert "2 diffusion(s) pour 2 prévue(s) ✅" in out


def test_message_duree_identique_mais_titre_du_plan_non_compte():
    # Un cantique PLANIFIÉ de même durée que le message ne doit pas passer
    # pour une diffusion du message.
    plan = plan_2_blocs()
    plan["blocks"][0]["items"].append(
        {"type": "louange", "title": "Cantique long", "duration_seconds": 1800})
    h = [entry("pqe j1", 0, 2, duration=1800),
         entry("Cantique long", 2, 0, duration=1800),
         entry("pqe j1", 6, 0, duration=1800, playlist="BLOC_B_SERIE_DU_JOUR")]
    out = build_health_section(h, JOUR, plan)
    assert "2 diffusion(s) pour 2 prévue(s) ✅" in out


def test_health_ignore_les_entrees_du_lendemain():
    # Régression 11/07/2026 : les 15 min de débordement de fetch_history()
    # retombaient dans la fenêtre BLOC_A (00:00-06:00) — 3 jingles du
    # lendemain comptés, « 9/9 » affiché au lieu de 6/9.
    lendemain = int(datetime(2026, 6, 26, 0, 1, 30, tzinfo=timezone.utc).timestamp())
    h = [entry("jingle avant message 01", 0, 1, duration=10),
         entry("pqe j1", 0, 2, duration=1800),
         entry("pqe j1", 6, 0, duration=1800, playlist="BLOC_B_SERIE_DU_JOUR"),
         {"played_at": lendemain, "duration": 10, "playlist": "BLOC_A_SERIE_DU_JOUR",
          "song": {"title": "jingle avant bible 02"}},
         {"played_at": lendemain + 15, "duration": 1800,
          "playlist": "BLOC_A_SERIE_DU_JOUR", "song": {"title": "pqe j1"}}]
    out = build_health_section(h, JOUR, plan_2_blocs())
    assert "BLOC_A 1/2" in out                       # pas le jingle du lendemain
    assert "2 diffusion(s) pour 2 prévue(s) ✅" in out  # pas le message du lendemain


def test_plan_section_ignore_les_entrees_du_lendemain():
    plan = {"blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"title": "Amos 1"}, {"title": "Amos 2"}]}]}
    lendemain = int(datetime(2026, 6, 26, 0, 1, 30, tzinfo=timezone.utc).timestamp())
    h = hist(("Amos 1", 1), ("Amos 2", 2)) + [
        {"played_at": lendemain, "song": {"title": "AzuraCast is Live!"}}]
    out = build_plan_section(h, date(2026, 6, 25), plan)
    assert "conformité 100%" in out
    assert "en trop  0" in out
    assert "AzuraCast is Live!" not in out


def test_plan_section_message_tag_fichier_different_reste_conforme():
    # Même régression que côté santé : le message joué sous son tag fichier
    # ne doit plus compter « sauté » + « en trop » dans chaque bloc.
    plan = {"message": {"title": "Tian Le pardon 1", "duration_seconds": 614},
            "blocks": [{"block_name": "BLOC_A_SERIE_DU_JOUR", "window": "00:00-06:00",
                        "items": [{"type": "message", "title": "Tian Le pardon 1",
                                   "duration_seconds": 614},
                                  {"type": "bible", "title": "Amos 1"}]}]}
    h = [entry("La pardon", 0, 2, duration=614),
         entry("Amos 1", 0, 32, duration=300)]
    out = build_plan_section(h, JOUR, plan)
    assert "conformité 100%" in out
    assert "sautés  0" in out
    assert "en trop  0" in out


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


def test_dernier_titre_du_jour_diffuse_contre_le_lendemain():
    # fetch_history() élargit désormais la fenêtre de 15 min sur le lendemain
    # pour que le dernier titre du jour ait une entrée "suivante" à comparer
    # (sinon il reste éternellement "durée réelle inconnue"). Cette entrée du
    # lendemain ne doit jamais apparaître dans le rapport affiché ni le bilan.
    lendemain = int(datetime(2026, 6, 26, 0, 1, 30, tzinfo=timezone.utc).timestamp())
    h = [entry("a", 23, 0, duration=60),
         entry("dernier", 23, 1, duration=90),
         {"played_at": lendemain, "duration": 8, "playlist": "BLOC_A_SERIE_DU_JOUR",
          "song": {"title": "premier titre du lendemain"}}]
    out, problems = build_report(h, JOUR)
    assert "dernier" in out
    assert "premier titre du lendemain" not in out
    assert "2 titres joués" in out
    assert "Bilan : 2 titres" in out
    assert "⏳ dernier titre" not in out


# ── Moniteur : corrélation des 3 rapports + plan ────────────────────────────

def srv(h, m, s, text):
    """Ligne liquidsoap_events datée (format serveur, heures UTC)."""
    return f"2026/06/25 {h:02d}:{m:02d}:{s:02d} {text}"


def test_classify_server_line_categorise_les_incidents():
    assert classify_server_line("[threads:1] PANIC: Liquidsoap has crashed") == "crash"
    assert classify_server_line("[lang:2] Could not perform http request: CurlException") == "network"
    assert classify_server_line("[safe_fallback:3] Switch to error_jingle.") == "deadair"
    assert classify_server_line("[source:3] track skip requested") == "skip"


def test_classify_server_line_ignore_le_bruit_benin():
    # Fins de décodage normales, dépréciations, préparations = pas des incidents.
    assert classify_server_line('[decoder:2] Decoding "x.mp3" ended: Ffmpeg_decoder.End_of_file.') == ""
    assert classify_server_line('[lang.deprecated:2] WARNING: "map_metadata" is deprecated') == ""
    assert classify_server_line('[next_song:3] Prepared "/media/jingle.mp3" (RID 14).') == ""


def test_parse_server_events_filtre_par_jour_et_categorie():
    text = "\n".join([
        srv(0, 1, 22, "[lang:2] Could not perform http request: CurlException"),
        srv(0, 1, 22, "[threads:1] PANIC: Liquidsoap has crashed, exiting."),
        srv(0, 1, 26, '[decoder:2] Decoding "x.mp3" ended: Ffmpeg_decoder.End_of_file.'),
        "2026/06/26 05:00:00 [threads:1] PANIC: crash du lendemain",  # autre jour
        "ligne sans horodatage à ignorer",
    ])
    events = parse_server_events(text, JOUR)
    cats = [e.category for e in events]
    assert cats == ["network", "crash"]  # benin + lendemain + non daté écartés


def test_group_incidents_regroupe_les_rafales():
    events = parse_server_events("\n".join([
        srv(0, 1, 22, "[threads:2] Queue #1 crashed with exception"),
        srv(0, 1, 23, "[threads:1] PANIC: Liquidsoap has crashed"),  # même rafale
        srv(6, 0, 0, "[threads:1] PANIC: autre crash 6h plus tard"),
    ]), JOUR)
    groups = group_incidents(events)
    assert len(groups) == 2
    assert groups[0]["count"] == 2
    assert groups[1]["count"] == 1


def test_playback_incidents_reprend_coupures_et_trous():
    # a coupé (réel 10s pour 600s), trou après b (réel 600s pour 60s), c normal.
    h = [entry("a", 0, 0, duration=600), entry("b", 0, 0, 10, duration=60),
         entry("c", 0, 10, 10, duration=60), entry("d", 0, 11, 10, duration=60)]
    inc = playback_incidents(h, JOUR)
    kinds = {i["kind"] for i in inc}
    assert "COUPÉ" in kinds and "TROU" in kinds


def test_summarize_watch_detecte_restart_et_doublon():
    """Le doublon qui compte porte sur du contenu long (ici le message)."""
    text = "\n".join([
        '{"logged_at": "2026-06-25T00:02:04+00:00", "check": 1, "now_playing_title": "",'
        ' "started_after_restart": true, "queue_preview": ['
        '{"title": "PQE J 1", "is_played": false},'
        '{"title": "PQE J 1", "is_played": false}]}',  # message en double
    ])
    summary = summarize_watch(parse_watch_records(text))
    assert summary["restart"] is True
    assert summary["dup_seen"] is True
    assert summary["first"] == "00:02:04"


def test_summarize_watch_ignore_un_jingle_en_double():
    """Faux positif historique : juste apres un restart, l'apercu de file
    contient normalement 2x le meme jingle. 29 alertes sur 41 nuits en
    aout-septembre 2026, zero double diffusion derriere."""
    text = ('{"logged_at": "2026-06-25T00:02:04+00:00", "now_playing_title": "",'
            ' "started_after_restart": true, "queue_preview": ['
            '{"title": " - jingle avant message 04", "is_played": false},'
            '{"title": " - jingles de transition 1", "is_played": false},'
            '{"title": " - jingle avant message 04", "is_played": false},'
            '{"title": "PQE J 1", "is_played": false}]}')
    assert summarize_watch(parse_watch_records(text))["dup_seen"] is False


def test_summarize_watch_detecte_le_titre_a_l_antenne_en_file():
    """Motif de la garde de frontiere : le message joue est deja re-empile."""
    text = ('{"logged_at": "2026-06-25T06:32:57+00:00", "started_after_restart": true,'
            ' "now_playing_title": "PQE J 1", "queue_preview": ['
            '{"title": " - jingle avant message 05", "is_played": false},'
            '{"title": "PQE J 1", "is_played": false}]}')
    assert summarize_watch(parse_watch_records(text))["dup_seen"] is True


def test_summarize_watch_file_saine():
    text = ('{"logged_at": "2026-06-25T00:02:04+00:00", "started_after_restart": true,'
            ' "queue_preview": [{"title": "a", "is_played": false},'
            ' {"title": "b", "is_played": false}]}')
    summary = summarize_watch(parse_watch_records(text))
    assert summary["dup_seen"] is False
    assert summarize_watch([]) is None


def test_nearest_incident_dans_la_fenetre():
    groups = group_incidents(parse_server_events(
        srv(14, 31, 58, "[safe_fallback:3] Switch to error_jingle."), JOUR))
    at_anomaly = datetime(2026, 6, 25, 14, 32, 5, tzinfo=timezone.utc)
    far = datetime(2026, 6, 25, 20, 0, 0, tzinfo=timezone.utc)
    assert nearest_incident(at_anomaly, groups) is not None
    assert nearest_incident(far, groups) is None


def test_monitor_correle_une_coupure_avec_un_crash_serveur():
    # Coupure à 14:01:30 (fichier 600s, coupé à 8s) causée par le crash 14:01:22.
    # En pleine journée : hors des fenêtres rotation/reset, donc vrai incident.
    h = [entry("Message du jour", 14, 1, 22, duration=600),
         entry("suite", 14, 1, 30, duration=600)]
    logs = {
        "server": "\n".join([
            srv(14, 1, 22, "[lang:2] Could not perform http request: CurlException"),
            srv(14, 1, 22, "[threads:1] PANIC: Liquidsoap has crashed, exiting."),
        ]),
        "midnight": '{"logged_at": "2026-06-25T00:02:04+00:00",'
                    ' "started_after_restart": true, "queue_preview": []}',
        "boundary": "",
    }
    out = build_monitor_section(h, JOUR, plan_2_blocs(), logs)
    assert "MONITEUR RADIO — 2026-06-25" in out
    assert "incident(s) détecté(s)" in out
    assert "crash Liquidsoap" in out
    assert "RESET MINUIT : restart confirmé vers 00:02:04" in out
    assert "INCIDENTS CORRÉLÉS" in out
    assert "cause probable 14:01:22" in out


def test_monitor_ras_quand_tout_va_bien():
    h = [entry("a", 0, 0, duration=60), entry("b", 0, 1, duration=60)]
    logs = {"server": srv(3, 0, 0,
                          '[decoder:2] Decoding "x.mp3" ended: Ffmpeg_decoder.End_of_file.'),
            "midnight": "", "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_2_blocs(), logs)
    assert "État : ✅ RAS" in out
    assert "SERVEUR : aucun incident" in out
    assert "aucune anomalie de diffusion à corréler ✅" in out


def test_monitor_signale_archives_absentes():
    h = [entry("a", 14, 0, duration=600), entry("b", 14, 0, 8, duration=600)]
    logs = {"server": "", "midnight": "", "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_2_blocs(), logs)
    assert "archive liquidsoap_events absente" in out
    assert "aucun instantané de surveillance" in out
    assert "archive serveur absente — cause non déterminable" in out


# ── Fenêtres de maintenance : le bruit que le système s'inflige à lui-même ────
# Août 2026 : 4 296 des 4 341 événements serveur retenus (99 %) venaient de la
# rotation et du reset, et le rapport titrait « ❌ incident » 31 jours sur 31.

def test_rotation_produit_des_echecs_reseau_attendus():
    """23h32-23h36 : l'AutoDJ échoue à précharger pendant que la rotation
    reconstruit les blocs. BLOC_E (statique) est à l'antenne : aucun effet."""
    assert is_expected_incident("network", time(23, 32)) is True
    assert is_expected_incident("network", time(23, 36)) is True


def test_reset_de_minuit_produit_crash_et_bascule_attendus():
    assert is_expected_incident("crash", time(0, 1, 22)) is True
    assert is_expected_incident("deadair", time(0, 1, 31)) is True
    assert is_expected_incident("network", time(0, 1, 20)) is True


@pytest.mark.parametrize("categorie,moment", [
    ("deadair", time(5, 59)),    # assèchement frontière BLOC_A→B (vrai défaut)
    ("deadair", time(11, 59)),
    ("deadair", time(17, 59)),
    ("deadair", time(23, 29)),   # juste AVANT la fenêtre de rotation
    ("crash", time(14, 0)),      # un crash en journée reste un incident
    ("network", time(8, 0)),
    ("network", time(23, 41)),   # juste APRÈS la fenêtre de rotation
    ("skip", time(0, 1)),        # un saut de fichier n'est jamais « attendu »
])
def test_hors_fenetre_ou_hors_categorie_reste_un_incident(categorie, moment):
    assert is_expected_incident(categorie, moment) is False


def test_bornes_des_fenetres_sont_inclusives():
    assert in_window(time(23, 30), ROTATION_WINDOW) is True
    assert in_window(time(23, 40), ROTATION_WINDOW) is True
    assert in_window(time(23, 29, 59), ROTATION_WINDOW) is False
    assert in_window(time(0, 3), MIDNIGHT_RESET_WINDOW) is True
    assert in_window(time(0, 3, 1), MIDNIGHT_RESET_WINDOW) is False


def test_moniteur_reste_vert_sur_le_bruit_de_rotation():
    """Une journée saine avec la rafale de rotation ne doit plus titrer ❌."""
    h = [entry("a", 14, 0, duration=60), entry("b", 14, 1, duration=60)]
    logs = {"server": "\n".join(srv(23, 32, s, "[request.dynamic:3] Fetch failed: retry.")
                                for s in range(0, 50, 5)),
            "midnight": "", "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_2_blocs(), logs)
    assert "❌" not in out
    assert "ATTENDU" in out and "hors verdict" in out
    assert "serveur : 0 incident(s)" in out


def test_moniteur_reste_rouge_sur_un_assechement_de_frontiere():
    """L'assèchement de 17h59 met « AzuraCast is Live! » à l'antenne : réel."""
    h = [entry("a", 14, 0, duration=60), entry("b", 14, 1, duration=60)]
    logs = {"server": srv(17, 59, 5, "[safe_fallback:3] Switch to error_jingle."),
            "midnight": "", "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_2_blocs(), logs)
    assert "❌ incident(s) détecté(s)" in out
    assert "serveur : 1 incident(s)" in out


def test_coupure_par_le_reset_de_minuit_sort_du_verdict():
    """Les 20 anomalies d'août étaient toutes ce cas : dernier cantique de
    BLOC_E tronqué par le redémarrage. 29 jours sur 31 rouges pour ça."""
    # Le cantique démarre à 23h55 et s'arrête à 00h01:40 (400s au lieu de 600) :
    # le titre suivant appartient au LENDEMAIN, comme dans l'historique réel.
    lendemain = int(datetime(2026, 6, 26, 0, 1, 40, tzinfo=timezone.utc).timestamp())
    h = [entry("cantique", 23, 55, duration=600),
         {"played_at": lendemain, "duration": 120, "playlist": "000_TRANSITION",
          "song": {"title": "jingles de transition 1"}}]
    logs = {"server": "", "midnight": "", "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_2_blocs(), logs)
    assert "❌" not in out
    assert "tronqué(s) par le redémarrage de minuit" in out
    assert "diffusion : 0 coupure(s)" in out


def test_coupure_en_journee_reste_dans_le_verdict():
    h = [entry("message", 14, 0, duration=600), entry("suite", 14, 0, 8, duration=600)]
    logs = {"server": "", "midnight": "", "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_2_blocs(), logs)
    assert "❌ incident(s) détecté(s)" in out
    assert "diffusion : 1 coupure(s)" in out


def test_diffusion_du_message_en_trop_compte_meme_sans_double_rapproche():
    """01/09/2026 : message passé 5 fois pour 4 prévues, espacées de plus de
    15 min. Le verdict ne le voyait pas (il ne comptait que le « rapproché »)."""
    plan = plan_2_blocs()   # 2 blocs → 2 diffusions attendues
    h = [entry("PQE J 1", 0, 5, duration=1800),
         entry("PQE J 1", 6, 5, duration=1800),
         entry("PQE J 1", 14, 5, duration=1800)]   # la 3e est en trop
    logs = {"server": "", "midnight": "", "boundary": ""}
    out = build_monitor_section(h, JOUR, plan, logs)
    assert "❌ incident(s) détecté(s)" in out
    assert "1 double(s) message" in out


# ── Ponctualité : le retard des opérations planifiées ────────────────────────
# Du 15/10 au 17/11/2026, cron-job.org est resté muet 32 nuits ; le cron GitHub
# de secours a rattrapé avec +189 min (rotation) et +228 min (reset) de retard
# médian, sans que rien ne le signale. Ces tests verrouillent les trois
# comportements qui manquaient (AUDIT_2026-11-17.md §3.1, §3.2 et §4).

def plan_date_a(generated_at):
    """Plan de référence, horodaté à l'heure réelle de la rotation."""
    plan = plan_2_blocs()
    plan["generated_at"] = generated_at
    return plan


def surveillance_a(heure):
    """Instantané de surveillance de minuit à l'heure réelle du restart."""
    return ('{"logged_at": "2026-06-25T' + heure + '+00:00",'
            ' "started_after_restart": true, "queue_preview": []}')


def test_delay_minutes_lit_un_retard_qui_franchit_minuit():
    # Rotation prévue 23h30, exécutée à 02h56 le lendemain : +206 min, pas -1234.
    assert delay_minutes(time(2, 56), ROTATION_SCHEDULED) == 206
    assert delay_minutes(time(23, 31), ROTATION_SCHEDULED) == 1
    assert delay_minutes(time(3, 47), RESET_SCHEDULED) == 227


def test_is_on_time_tolere_la_gigue_du_declencheur_externe():
    # Le déclencheur en bon état arrive à +0,7 min de médiane ; le secours
    # jamais sous +110 min. La tolérance doit trancher net entre les deux.
    assert is_on_time(time(0, 2), RESET_SCHEDULED) is True
    assert is_on_time(time(0, PUNCTUALITY_TOLERANCE_MINUTES), RESET_SCHEDULED) is True
    assert is_on_time(time(0, PUNCTUALITY_TOLERANCE_MINUTES + 1), RESET_SCHEDULED) is False
    assert is_on_time(None, RESET_SCHEDULED) is True   # archive absente ≠ incident


def test_window_around_encadre_lhorodatage_et_borne_la_journee():
    # L'horodatage marque la FIN de l'opération : la fenêtre s'ouvre avant.
    assert window_around(time(3, 2), 10, 2) == (time(2, 52), time(3, 4))
    # Bornes de journée : ni avant 00:00:00, ni après 23:59:59.
    assert window_around(time(0, 1, 56), 3, 2) == (time(0, 0), time(0, 3, 56))
    assert window_around(time(23, 58), 10, 5) == (time(23, 48), time(23, 59, 59))


def test_watch_time_et_plan_time_lisent_les_heures_reelles():
    assert watch_time(summarize_watch(parse_watch_records(
        surveillance_a("03:47:12")))) == time(3, 47, 12)
    assert watch_time(None) is None
    assert plan_time(plan_date_a("2026-06-25T02:56:04.123456+00:00")) == time(2, 56, 4)
    assert plan_time(plan_2_blocs()) is None          # plan sans horodatage
    assert plan_time({"generated_at": "pas une date"}) is None


def test_rotation_en_retard_deplace_la_fenetre_des_echecs_reseau():
    """La rafale « Fetch failed » suit la rotation, pas l'horloge.

    C'est l'artefact qui a produit ~140 faux incidents serveur par jour depuis
    le 16/10 : les mêmes rafales, hors de la fenêtre figée 23h30-23h40."""
    tardive = time(3, 2)   # heure du plan ; la rafale la précède de ~4 min
    assert is_expected_incident("network", time(2, 58), rotation_at=tardive) is True
    # Et l'ancienne fenêtre ne protège plus rien ce jour-là.
    assert is_expected_incident("network", time(23, 32), rotation_at=tardive) is False
    # Journée normale : la rafale de 23:32 précède un plan écrit à 23:36.
    assert is_expected_incident("network", time(23, 32, 35),
                                rotation_at=time(23, 36)) is True


def test_reset_tardif_rend_la_bascule_sur_silence_bien_reelle():
    """Un restart à 03h47 n'est plus couvert par les 2 min de 000_TRANSITION :
    la bascule sur le jingle d'erreur passe à l'antenne. 90 cas sur 32 nuits."""
    tardif = time(3, 47)   # 1er contrôle de surveillance, ~40 s après le restart
    assert is_expected_incident("deadair", time(3, 46), reset_at=tardif) is False
    assert is_expected_incident("crash", time(3, 46), reset_at=tardif) is False
    # Le bruit d'API reste inaudible, lui, même en retard.
    assert is_expected_incident("network", time(3, 46), reset_at=tardif) is True


def test_reset_a_lheure_garde_sa_bascule_attendue():
    ponctuel = time(0, 1, 56)
    assert is_expected_incident("deadair", time(0, 1, 20), reset_at=ponctuel) is True
    assert is_expected_incident("crash", time(0, 1, 14), reset_at=ponctuel) is True
    # Hors de la rafale de 3 min, même à l'heure, c'est un incident.
    assert is_expected_incident("deadair", time(0, 30), reset_at=ponctuel) is False


def test_titre_tronque_par_un_reset_tardif_est_une_vraie_anomalie():
    # Titre de 10 min commencé à 03h40, coupé net à 03h47 par le restart.
    coupe = {"dt": datetime(2026, 6, 25, 3, 40, tzinfo=timezone.utc),
             "actual": 400, "title": "Amos 1"}
    assert _cut_by_midnight_reset(coupe, reset_at=time(3, 47)) is False
    # Le même titre, tronqué par un reset ponctuel à minuit : conséquence connue.
    nuit = {"dt": datetime(2026, 6, 25, 0, 0, tzinfo=timezone.utc),
            "actual": 75, "title": "dernier cantique"}
    assert _cut_by_midnight_reset(nuit, reset_at=time(0, 1, 56)) is True


def test_monitor_passe_au_rouge_sur_un_retard_seul():
    """Le défaut central de l'audit : une journée sans aucune anomalie de
    diffusion mais avec un reset 3 h 47 en retard titrait « ✅ RAS »."""
    h = [entry("a", 8, 0, duration=60), entry("b", 8, 1, duration=60)]
    logs = {"server": "", "midnight": surveillance_a("03:47:12"), "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_date_a("2026-06-25T02:56:04+00:00"), logs)
    assert "État : ❌ incident(s) détecté(s)" in out
    assert "ponctualité : rotation +206 min, reset de minuit +227 min" in out
    assert "PONCTUALITÉ : ❌" in out
    assert "rotation à 02h56 pour 23h30 (+206 min)" in out
    assert "reset de minuit à 03h47 pour 00h00 (+227 min)" in out
    assert "cron-job.org" in out


def test_monitor_ponctualite_verte_quand_tout_est_a_lheure():
    h = [entry("a", 8, 0, duration=60), entry("b", 8, 1, duration=60)]
    logs = {"server": "", "midnight": surveillance_a("00:02:04"), "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_date_a("2026-06-24T23:31:10+00:00"), logs)
    assert "PONCTUALITÉ : ✅" in out
    assert "rotation à 23h31 pour 23h30 (+1 min)" in out
    assert "❌" not in out


def test_monitor_dit_quand_les_heures_sont_inconnues():
    h = [entry("a", 8, 0, duration=60), entry("b", 8, 1, duration=60)]
    out = build_monitor_section(h, JOUR, plan_2_blocs(),
                                {"server": "", "midnight": "", "boundary": ""})
    assert "PONCTUALITÉ : heures d'exécution inconnues" in out
    # Une archive manquante ne doit pas inventer un incident.
    assert "État : ✅ RAS" in out


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))


# ── Rotation du soir : la 2e rotation qui touche une même journée ────────────
# Depuis le retour à l'heure du déclencheur (24/11/2026), chaque journée se
# termine sur la rotation qui prépare le lendemain. Sa rafale réseau ne tombait
# dans aucune fenêtre : 47 événements comptés comme incidents le 25/11/2026,
# donc un verdict ❌ alors que la journée n'avait eu ni coupure ni doublon.
# Un verdict toujours rouge finit par ne plus être lu (AUDIT_2026-11-17.md §3.6).

def test_evening_rotation_time_lit_le_plan_du_lendemain():
    # Rotation du 25 à 23h36 : elle écrit le plan du 26, mais sa rafale est
    # bien tombée pendant la journée du 25.
    assert evening_rotation_time(
        plan_date_a("2026-06-25T23:36:32+00:00"), JOUR) == time(23, 36, 32)
    # Partie après minuit : elle appartient au 26, où plan_time la couvre déjà.
    assert evening_rotation_time(
        plan_date_a("2026-06-26T00:12:00+00:00"), JOUR) is None
    assert evening_rotation_time(None, JOUR) is None
    assert evening_rotation_time(plan_2_blocs(), JOUR) is None   # sans horodatage


def test_rafale_de_la_rotation_du_soir_est_attendue():
    soir = time(23, 36, 32)        # generated_at du plan du lendemain
    veille = time(23, 7, 1)        # rotation qui a préparé CETTE journée
    assert is_expected_incident("network", time(23, 32, 59),
                                rotation_at=veille,
                                evening_rotation_at=soir) is True
    # Sans le plan du lendemain, la même rafale reste un incident : c'est l'état
    # d'avant le correctif, et le cas réel du 25/11/2026.
    assert is_expected_incident("network", time(23, 32, 59),
                                rotation_at=veille) is False
    # La règle reste étroite : la rotation ne redémarre pas Liquidsoap, donc un
    # silence à cette heure-là est bien réel.
    assert is_expected_incident("deadair", time(23, 32, 59),
                                rotation_at=veille,
                                evening_rotation_at=soir) is False


def test_monitor_ne_rougit_plus_pour_la_rotation_du_soir():
    h = [entry("a", 0, 0, duration=60), entry("b", 0, 1, duration=60)]
    rafale = "\n".join(
        srv(23, 32, 59, "[lang:2] Could not perform http request: CurlException")
        for _ in range(3))
    logs = {"server": rafale, "midnight": "", "boundary": ""}

    # Plan du jour écrit la veille à 23h07 : la fenêtre attendue est 22h57-23h09.
    plan_du_jour = plan_date_a("2026-06-24T23:07:01+00:00")

    sans_plan = build_monitor_section(h, JOUR, plan_du_jour, logs)
    assert "incident(s) détecté(s)" in sans_plan

    avec_plan = build_monitor_section(h, JOUR, plan_du_jour, logs,
                                      plan_date_a("2026-06-25T23:36:32+00:00"))
    # La rafale reste affichée — rien n'est masqué — mais elle ne pilote plus
    # le verdict : ⚠️ RAS, le libellé réservé aux suites connues des opérations.
    assert "⚠️ RAS — seules les suites connues" in avec_plan
    assert "incident(s) détecté(s)" not in avec_plan
    assert "serveur : 0 incident(s)" in avec_plan
    assert "rotation du soir, qui prépare le lendemain (23h26-23h38)" in avec_plan
    assert "23:32 🌐 échec réseau" in avec_plan
