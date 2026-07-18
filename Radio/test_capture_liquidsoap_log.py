"""Tests de la capture des événements du liquidsoap.log.
Fonctions pures uniquement (aucun appel réseau)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from capture_liquidsoap_log import append_events, extract_new_events

LOG = """\
[mp3 @ 0x7f4d501b02c0] Estimating duration from bitrate, this may be inaccurate
2026/07/17 10:30:33 [next_song:3] Prepared "/var/azuracast/stations/evangile_du_royaume/media/La bible/esdras_008.mp3" (RID 170).
2026/07/17 10:30:33 [cue_next_song:3] Cueing in...
2026/07/17 12:00:13 [decoder.id3:2] Error while decoding file tags: Invalid_argument("String.sub / Bytes.sub")
[mp3float @ 0x7f4d501d04c0] Could not update timestamps for skipped samples.
2026/07/17 23:32:52 [request.dynamic:3] Fetch failed: retry.
2026/07/18 00:01:05 [next_song:3] Prepared "/var/azuracast/media/jingle_09.mp3" (RID 412).
"""


def test_garde_les_lignes_d_interet_datees():
    events = extract_new_events(LOG, last_ts="")
    lignes = [line for (_, line) in events]
    assert any("Prepared" in l and "esdras_008" in l for l in lignes)
    assert any("decoder.id3:2" in l for l in lignes)
    assert any("Fetch failed" in l for l in lignes)


def test_ecarte_le_bruit_non_date_et_l_info_courante():
    events = extract_new_events(LOG, last_ts="")
    lignes = [line for (_, line) in events]
    # Bruit ffmpeg sans horodatage : inutilisable pour la corrélation.
    assert not any("mp3float" in l or "Estimating duration" in l for l in lignes)
    # Ligne info niveau 3 sans mot-clé d'incident.
    assert not any("Cueing in" in l for l in lignes)


def test_last_ts_dedoublonne_les_captures_qui_se_chevauchent():
    premiere = extract_new_events(LOG, last_ts="")
    seconde = extract_new_events(LOG, last_ts=premiere[-1][0])
    assert seconde == []
    partielle = extract_new_events(LOG, last_ts="2026/07/17 12:00:13")
    assert [ts for (ts, _) in partielle] == ["2026/07/17 23:32:52", "2026/07/18 00:01:05"]


def test_repartition_par_jour_de_l_horodatage(tmp_path):
    events = extract_new_events(LOG, last_ts="")
    counts = append_events(events, tmp_path)
    assert counts == {"2026-07-17": 3, "2026-07-18": 1}
    fichier_17 = (tmp_path / "liquidsoap_events_2026-07-17.log").read_text(encoding="utf-8")
    fichier_18 = (tmp_path / "liquidsoap_events_2026-07-18.log").read_text(encoding="utf-8")
    assert "esdras_008" in fichier_17 and "jingle_09" in fichier_18


def test_append_est_cumulatif(tmp_path):
    events = extract_new_events(LOG, last_ts="")
    append_events(events, tmp_path)
    append_events(extract_new_events(LOG.replace("23:32:52", "23:40:00"),
                                     last_ts="2026/07/17 23:33:00"), tmp_path)
    fichier = (tmp_path / "liquidsoap_events_2026-07-17.log").read_text(encoding="utf-8")
    assert fichier.count("Fetch failed") == 2
