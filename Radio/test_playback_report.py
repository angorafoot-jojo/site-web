"""Tests de la section « réel vs prévu » du rapport de diffusion.
Fonctions pures uniquement (aucun appel réseau)."""
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from playback_report import (norm_title, build_plan_section, build_health_section,
                             build_report, _window_bounds,
                             classify_server_line, parse_server_events,
                             group_incidents, playback_incidents,
                             parse_watch_records, summarize_watch,
                             nearest_incident, build_monitor_section,
                             parse_prepared_files, title_from_media_path,
                             playlist_from_source, resolve_missing_titles,
                             load_sibling_logs, TITLE_SOURCE_KEY)

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
    text = "\n".join([
        '{"logged_at": "2026-06-25T00:02:04+00:00", "check": 1, "now_playing_title": "",'
        ' "started_after_restart": true, "queue_preview": ['
        '{"title": "jingle x", "is_played": false},'
        '{"title": "jingle x", "is_played": false}]}',  # doublon dans la file
    ])
    summary = summarize_watch(parse_watch_records(text))
    assert summary["restart"] is True
    assert summary["dup_seen"] is True
    assert summary["first"] == "00:02:04"


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
    # Coupure à 00:01:30 (fichier 600s, coupé à 8s) causée par le crash 00:01:22.
    h = [entry("Message du jour", 0, 1, 22, duration=600),
         entry("suite", 0, 1, 30, duration=600)]
    logs = {
        "server": "\n".join([
            srv(0, 1, 22, "[lang:2] Could not perform http request: CurlException"),
            srv(0, 1, 22, "[threads:1] PANIC: Liquidsoap has crashed, exiting."),
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
    assert "cause probable 00:01:22" in out


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
    h = [entry("a", 0, 0, duration=600), entry("b", 0, 0, 8, duration=600)]
    logs = {"server": "", "midnight": "", "boundary": ""}
    out = build_monitor_section(h, JOUR, plan_2_blocs(), logs)
    assert "archive liquidsoap_events absente" in out
    assert "aucun instantané de surveillance" in out
    assert "archive serveur absente — cause non déterminable" in out


# ── Identification des titres qu'AzuraCast n'a pas su nommer ────────────────
# Cas réel : au restart de minuit, Liquidsoap joue un jingle via sa source de
# repli, hors file AutoDJ — AzuraCast journalise l'entrée sans titre ni
# playlist et le rapport affichait « ? » (14 fois du 30/06 au 01/08/2026).

MEDIA = "/var/azuracast/stations/evangile_du_royaume/media"


def prep(h, m, s, source, path):
    """Ligne « Prepared » du log Liquidsoap."""
    return f'2026/06/25 {h:02d}:{m:02d}:{s:02d} [{source}:3] Prepared "{path}" (RID 11).'


def sans_titre(h, m, s):
    """Entrée d'historique arrivée sans métadonnée (repli hors AutoDJ)."""
    return {"played_at": ts(h, m, s), "duration": 95, "playlist": "", "song": {"title": ""}}


def test_titre_deduit_du_chemin_du_media():
    assert title_from_media_path(f"{MEDIA}/jingles_de_transition_1.mp3") \
        == "jingles de transition 1"
    assert title_from_media_path(f"{MEDIA}/La bible/genèse_001.mp3") == "genèse 001"


def test_titre_hors_mediatheque_est_signale_comme_tel():
    # error.mp3 d'Icecast : « error » tout court n'apprendrait rien au lecteur.
    out = title_from_media_path("/usr/local/share/icecast/web/error.mp3")
    assert out == "error (fichier serveur, hors médiathèque)"


def test_playlist_deduite_de_la_source_liquidsoap():
    assert playlist_from_source("playlist_000_transition") == "000_TRANSITION"
    assert playlist_from_source("playlist_bloc_a_serie_du_jour") == "BLOC_A_SERIE_DU_JOUR"
    # Sources qui ne portent aucune playlist : ne rien inventer.
    assert playlist_from_source("next_song") == ""
    assert playlist_from_source("error_jingle") == ""


def test_parse_prepared_garde_l_ordre_du_log_dans_la_seconde():
    # Bascule sur le jingle d'erreur puis reprise 1 s plus tard : c'est la
    # DERNIÈRE préparation qui tient l'antenne.
    text = "\n".join([
        prep(0, 1, 25, "error_jingle", "/usr/local/share/icecast/web/error.mp3"),
        prep(0, 1, 25, "playlist_000_transition", f"{MEDIA}/jingles_de_transition_1.mp3"),
        "ligne non datée ignorée",
    ])
    prepared = parse_prepared_files(text)
    assert [p[1] for p in prepared] == ["error_jingle", "playlist_000_transition"]


def test_titre_manquant_retrouve_dans_le_log_liquidsoap():
    history = [sans_titre(0, 1, 31)]
    server = "\n".join([
        prep(0, 1, 25, "error_jingle", "/usr/local/share/icecast/web/error.mp3"),
        prep(0, 1, 26, "playlist_000_transition", f"{MEDIA}/jingles_de_transition_1.mp3"),
    ])
    filled, unidentified = resolve_missing_titles(history, server)
    assert unidentified == []
    assert filled[0]["song"]["title"] == "jingles de transition 1"
    assert filled[0]["playlist"] == "000_TRANSITION"
    assert filled[0][TITLE_SOURCE_KEY] == "liquidsoap"
    # L'historique d'origine n'est pas modifié.
    assert history[0]["song"]["title"] == ""


def test_titre_connu_d_azuracast_n_est_jamais_ecrase():
    history = [entry("Genèse 1", 1, 18, 26, duration=348)]
    server = prep(1, 18, 21, "next_song", f"{MEDIA}/La bible/genèse_001.mp3")
    filled, _ = resolve_missing_titles(history, server)
    assert filled[0]["song"]["title"] == "Genèse 1"
    assert TITLE_SOURCE_KEY not in filled[0]


def test_prepared_trop_ancien_ou_posterieur_n_est_pas_apparie():
    history = [sans_titre(0, 10, 0)]
    trop_vieux = prep(0, 5, 0, "playlist_000_transition", f"{MEDIA}/vieux.mp3")
    posterieur = prep(0, 10, 5, "playlist_000_transition", f"{MEDIA}/suivant.mp3")
    filled, unidentified = resolve_missing_titles(history, f"{trop_vieux}\n{posterieur}")
    assert len(unidentified) == 1
    assert filled[0]["song"]["title"] == ""


def test_sans_archive_liquidsoap_le_titre_reste_non_identifie():
    filled, unidentified = resolve_missing_titles([sans_titre(0, 1, 31)], "")
    assert len(unidentified) == 1
    assert TITLE_SOURCE_KEY not in filled[0]


def test_rapport_affiche_la_provenance_du_titre_reconstitue():
    server = prep(0, 1, 26, "playlist_000_transition",
                  f"{MEDIA}/jingles_de_transition_1.mp3")
    history, _ = resolve_missing_titles(
        [sans_titre(0, 1, 31), entry("pqe j1", 0, 4, 42, duration=1800)], server)
    out, _ = build_report(history, JOUR)
    assert "jingles de transition 1   ← titre reconstitué depuis le log Liquidsoap" in out
    assert "  ?\n" not in out


def test_rapport_explicite_un_titre_non_identifiable():
    history, _ = resolve_missing_titles([sans_titre(0, 1, 31)], "")
    out, _ = build_report(history, JOUR)
    assert "ni métadonnée AzuraCast, ni trace Liquidsoap" in out


def test_moniteur_annonce_les_titres_retrouves():
    server = prep(0, 1, 26, "playlist_000_transition",
                  f"{MEDIA}/jingles_de_transition_1.mp3")
    history, _ = resolve_missing_titles([sans_titre(0, 1, 31)], server)
    out = build_monitor_section(history, JOUR, plan_2_blocs(),
                                {"server": server, "midnight": "", "boundary": ""})
    assert "IDENTIFICATION : 1 titre(s) sans métadonnée AzuraCast" in out
    assert "1 retrouvé(s) dans le log Liquidsoap ✅" in out
    assert "00:01:31  jingles de transition 1  (playlist 000_TRANSITION)" in out


def test_moniteur_muet_quand_tous_les_titres_sont_connus():
    h = [entry("pqe j1", 0, 1, duration=1800)]
    out = build_monitor_section(h, JOUR, plan_2_blocs(),
                                {"server": "", "midnight": "", "boundary": ""})
    assert "IDENTIFICATION" not in out


def test_titre_reconstitue_reste_un_bouche_trou():
    # Connaître le nom du jingle ne le rend pas prévu : il a joué hors AutoDJ,
    # le contrôle doit continuer à le signaler — avec son nom, cette fois.
    server = prep(0, 1, 26, "playlist_000_transition",
                  f"{MEDIA}/jingles_de_transition_1.mp3")
    history, _ = resolve_missing_titles(
        [sans_titre(0, 1, 31), entry("pqe j1", 0, 4, duration=1800)], server)
    out = build_health_section(history, JOUR, plan_2_blocs())
    assert "BOUCHE-TROUS : 1 titre(s)" in out
    assert "jingles de transition 1" in out
    assert "← titre reconstitué depuis le log Liquidsoap" in out


def test_prepared_de_la_veille_charge_pour_les_titres_d_apres_minuit(tmp_path):
    veille = f'2026/06/24 23:59:58 [playlist_000_transition:3] Prepared "{MEDIA}/x.mp3" (RID 1).'
    (tmp_path / "liquidsoap_events_2026-06-24.log").write_text(veille, encoding="utf-8")
    logs = load_sibling_logs(JOUR, tmp_path)
    assert logs["server_prev"] == veille
    # L'archive du jour reste vide : le moniteur doit continuer à le dire.
    assert logs["server"] == ""


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
