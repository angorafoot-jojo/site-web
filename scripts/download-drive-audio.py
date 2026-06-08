#!/usr/bin/env python3
"""
download-drive-audio.py
Télécharge tous les fichiers audio Google Drive du site.
Gère la page de confirmation Google Drive pour les gros fichiers.

Usage : python3 scripts/download-drive-audio.py
"""

import os
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

# ── Dossier de destination ───────────────────────────────────
DEST = os.path.join(os.path.dirname(__file__), "audio-downloads")
os.makedirs(DEST, exist_ok=True)

# ── Liste complète des fichiers ───────────────────────────────
FILES = [
    # ══ audios.html ══════════════════════════════════════════
    # [Revêtement spirituel]
    ("1ywmM-lgy2Ikt05wuBq9iMrPQGgKiIHU3", "audios_001_les-7-types-de-revetement-partie-4.mp3"),
    ("1kTynfxTAidfMsmlGpzhK3eEP_0_wdpNk", "audios_002_les-sept-types-de-revetement-partie-5.mp3"),
    # [Mariage · Royaume]
    ("1epc460ygrTFywEmpmRckhHDNuEbw-vn6", "audios_003_comment-gerer-son-mariage-partie-1.mp3"),
    ("18bwg4tJAgmHmfQlPOT_x5_-2KCc88x3-", "audios_004_comment-gerer-son-mariage-partie-2.mp3"),
    ("1sJY2VIJYt8R9TLzmLDyYI5PSM-IOSvOO", "audios_005_comment-gerer-son-mariage-partie-3.mp3"),
    # [Espérance]
    ("1YH_bfN1877Uvzh3E7DftU5dpV0KGI-u6", "audios_006_en-attendant-sa-bienheureuse-esperance-partie-1.mp3"),
    ("19PrBexsSiufxaQmxO5LvwpxJ_EvzQUQq", "audios_007_en-attendant-sa-bienheureuse-esperance-partie-2.mp3"),
    # [Repos]
    ("1JmTB3whK01xLMNs-AgIDjf9O3RQ4av5R", "audios_008_entrer-dans-son-repos-necessite.mp3"),
    ("17VtoswuFWWR_jWmLhNBFAR3Y2OlZ6YIg", "audios_009_entrer-dans-son-repos-intro-partie-1.mp3"),
    # [Le repos de YAHWEH]
    ("1-9f05t25l-4yi-yx-Ckd4NxpZ8fYW7A0", "audios_010_le-repos-de-yahweh-partie-1.mp3"),
    ("1BFDn6NdP9VulasTmiA8y0UEEOUeYV4CC", "audios_011_le-repos-de-yahweh-partie-2.mp3"),
    ("1dUkGxU5bG0aisXJBw-PpIu6Lfnj0KjDH", "audios_012_le-repos-de-yahweh-partie-3.mp3"),
    # [Doctrines fondamentales]
    ("19POZrgvkOR22_G58JesnF7Xa6jO19XBZ", "audios_013_les-doctrines-fondamentales-partie-1.mp3"),
    ("1FXG5DfejtwjhUzkw8dz5Yq4Th0UoV9TV", "audios_014_les-doctrines-fondamentales-partie-2.mp3"),
    ("1S2_BpC8l0emWkJxgh1EptFPIgjbNXsFZ", "audios_015_les-doctrines-fondamentales-partie-3.mp3"),
    ("1lI9P45jn-epcxbQrcJigs9GL15mdvYis", "audios_016_les-doctrines-fondamentales-partie-4.mp3"),
    ("1hMUv4EpUss-iNK0pv9aF1VjAHUSrwzxU", "audios_017_les-doctrines-fondamentales-partie-5.mp3"),
    # [Puits d'eau vive]
    ("1pHtbPN5aXfLQ8CaBQ5ijAqMGIDH9BGl-", "audios_018_puits-d-eau-vive-partie-1.mp3"),
    ("1G5dYqobe2pxkI0tsLaCNvPgRSshKkXa4", "audios_019_puits-d-eau-vive-partie-2.mp3"),
    ("1PVsFYRmdhZzjqVnuy1okhH89jL64l7Ur", "audios_020_puits-d-eau-vive-partie-3.mp3"),
    ("13qLqhOSxMnIfU8SaK1Gft4MT0JD6kdmI", "audios_021_puits-d-eau-vive-partie-4.mp3"),
    ("1MDYMKuV6lMqqyQuX94d6Z4wDWnAwRAH5", "audios_022_puits-d-eau-vive-parties-5-et-6.mp3"),
    # [Quiconque vit et croit]
    ("10Bd1HQCmwOJd_BK0yVR8203lppo0si6n", "audios_023_quiconque-vit-et-croit-partie-1.mp3"),
    ("1P-WJ-2lsnwSHUtYYj0bNkO8JLYtvXUU0", "audios_024_quiconque-vit-et-croit-partie-2.mp3"),
    ("1nXs--gUIelKICRjf1uwcI0jt-SFB3LXX", "audios_025_quiconque-vit-et-croit-partie-3.mp3"),
    # [Temps et saisons]
    ("1eQ1XpvuC_cHANcHjIkZo0mGKhTuwK8NB", "audios_026_temps-et-saisons-partie-1.mp3"),
    ("10fTznTTAl-jMuQH2mr-I2ZRxn6itok0R", "audios_027_temps-et-saisons-partie-2.mp3"),
    ("1TUMdUIsvIQcvL7GihBaAMMUXbWZJI4B4", "audios_028_temps-et-saisons-partie-3.mp3"),
    ("1ubhUZqonxP9rXFH0aS11MXdzj8lxooCJ", "audios_029_temps-et-saisons-partie-4.mp3"),
    # [Délivrance]
    ("1gb9Ev0Z0MrpxOHn4twOVquM9LUPsCKFI", "audios_030_la-delivrance-partie-1.mp3"),
    ("1y_l2V7aSIsUStIPwFw-IhoDOIUlGZvfj", "audios_031_la-delivrance-partie-2.mp3"),
    ("11DQ-UpGTPRZgTz2aWM7pcIP6JW8cO0Pj", "audios_032_la-delivrance-partie-3.mp3"),
    ("1RsCCiXqrB5nfe4WVHBPRoAplf98NpQJQ", "audios_033_la-delivrance-partie-4.mp3"),
    # [Enseignement]
    ("1EmXpny7so0aIVyFefXqsd1kCnfJ-bxje", "audios_034_le-sentier-du-repos.mp3"),
    ("1uRXDJPMpZfwK1kApiEtWWX8QyuuH4za1", "audios_035_le-rocher-des-ages.mp3"),

    # ══ podcasts.html ══════════════════════════════════════════
    # [Fondements]
    ("1dlMqM_rv-5UXqpd1BDdqvAl__AnQf0JG", "podcasts_001_fonde-et-enracine-dans-l-amour.mp3"),
    ("1z2MiPIzxzy587Wka-Ng09O-6XiehfRhY", "podcasts_002_oeuvre-de-la-foi-et-epreuve.mp3"),
    ("1V9fqWsP451YK4VSoEco9Y9Z-k7oiO-gV", "podcasts_003_doctrine-de-la-resurrection.mp3"),
    ("1BJ2g8RI17r6ZDu2fsWvQ8GEer7nP6swm", "podcasts_004_repentance-confession-restitution.mp3"),
    ("1_Nf2hyi4Uz6YAeAL-_vVvlgmj-86WLsu", "podcasts_005_action-de-graces.mp3"),
    # [Église · Royaume]
    ("1GQ3hVMUuqwtXsXaqYz7rrmY-z43_WiVj", "podcasts_006_du-stade-d-invites-a-appeles.mp3"),
    ("1ssHva52f_Wgsq2p_A8RkHZqqn1Db51h1", "podcasts_007_exercice-des-dons-face-au-monde.mp3"),
    ("1eCvWYHRtSqUG0uRb-Z5lRgEPNscp_bw8", "podcasts_008_dime-de-la-loi-a-la-grace.mp3"),
    ("1crU8lznoUqCDkAxJQW9ybVOGDiKYsH84", "podcasts_009_capacite-de-ramener-les-morts.mp3"),
    # [Vie spirituelle]
    ("1kJRswRssMiHbO1dsBZrrnZjxRpBqIMcz", "podcasts_010_l-eau-de-vie.mp3"),
    ("1xZC3iUuiGk7spIdC1nxCmlZeONv8Frrb", "podcasts_011_comment-mener-un-combat-spirituel.mp3"),
    # [Mariage · Famille]
    ("1udTINaOhdGKDw5mApmM6k5inaVSqFGAZ", "podcasts_012_l-eglise-de-christ-et-le-mariage.mp3"),
    ("1v3IguTB3Y-_jaBAPRY32IFPIv20Z4FUr", "podcasts_013_mariage-selon-le-modele-de-christ.mp3"),
    ("1tlMSWrtHiDnVwvuO5ykNJ8f3J12YSXYv", "podcasts_014_la-femme-est-la-gloire-de-l-homme.mp3"),
    # [Saint-Esprit]
    ("1gkYt11MpYjtw_JgKUpGG6WoMSk0SddUn", "podcasts_015_les-sept-esprits-de-dieu.mp3"),
    ("1jpGBBBoCxvRgNPOA0f5yvImV0X69n-R6", "podcasts_016_blaspheme-contre-le-saint-esprit.mp3"),
    ("1VKWVnck8yy0nH_dcG_C4Y3v1ECrQSgJg", "podcasts_017_revelation-connaissance-prophetie-doctrine.mp3"),
    # [Eschatologie]
    ("1T1xiHErxLmbWogwNyTFbpHkzCx0eGvvv", "podcasts_018_je-ferai-trembler-la-terre-et-le-ciel.mp3"),
    ("1aBCliW3u8tUxozn8_1zzKhxSrssLnC1I", "podcasts_019_parabole-des-dix-vierges.mp3"),
    ("1A6sKVgPpGFrBtGEv_HB-4CnUkdFXVply", "podcasts_020_esprits-des-justes-a-la-perfection.mp3"),
    ("1KOsI0hwEYx-0R8AEGM1VPWoUCbXMNe9R", "podcasts_021_quel-sort-reserve-aux-juifs.mp3"),
    # [Christ · Êtres célestes]
    ("1WlREC-38gyqCYBdoCTBV3r3P5a0WaZFl", "podcasts_022_jesus-christ-etoile-brillante-du-matin.mp3"),
    ("1JkuwtQGeQEuDQc2rFdcvSxzViAXDlpyE", "podcasts_023_difference-dieu-pere-et-jesus-christ.mp3"),
    ("1sD9L-aHOmzyGvvibjtl5VuPbIUJo6zDY", "podcasts_024_qui-est-l-ange-de-l-eternel.mp3"),
]

# ── Téléchargement ───────────────────────────────────────────

def human_size(n):
    for unit in ['o', 'Ko', 'Mo', 'Go']:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} Go"

def download(drive_id, filename):
    dest_path = os.path.join(DEST, filename)

    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 10_000:
        print(f"  ⏭  Déjà téléchargé : {filename}")
        return True

    # Cookiejar pour gérer la session Google
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'),
        ('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'),
    ]

    # Nouvelle URL Google Drive usercontent
    url = f"https://drive.usercontent.google.com/download?id={drive_id}&export=download&authuser=0&confirm=t"

    try:
        print(f"  ⬇  {filename}", end="", flush=True)
        response = opener.open(url, timeout=60)

        # Vérifier le Content-Type
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' in content_type:
            # Page de confirmation — extraire le token
            html = response.read().decode('utf-8', errors='ignore')
            token_m = re.search(r'name="confirm"\s+value="([^"]+)"', html)
            uuid_m  = re.search(r'name="uuid"\s+value="([^"]+)"', html)
            if token_m:
                params = urllib.parse.urlencode({
                    'id': drive_id,
                    'export': 'download',
                    'confirm': token_m.group(1),
                    'uuid': uuid_m.group(1) if uuid_m else '',
                })
                url2 = f"https://drive.usercontent.google.com/download?{params}"
                response = opener.open(url2, timeout=120)
            else:
                # Pas de token — essai direct avec confirm=t
                pass

        # Télécharger
        total = 0
        with open(dest_path, 'wb') as f:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
                print(f"\r  ⬇  {filename} — {human_size(total)}", end="", flush=True)

        size = os.path.getsize(dest_path)
        if size < 10_000:
            os.remove(dest_path)
            print(f"\r  ✗  {filename} — Fichier invalide ({human_size(size)}) — probablement privé ou expiré")
            return False

        print(f"\r  ✓  {filename} — {human_size(size)}                    ")
        return True

    except Exception as e:
        print(f"\r  ✗  {filename} — Erreur : {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False

# ── Main ─────────────────────────────────────────────────────
def main():
    print(f"\n{'═'*60}")
    print(f"  Téléchargement audio — L'Évangile du Royaume")
    print(f"  Destination : {DEST}")
    print(f"  Fichiers    : {len(FILES)}")
    print(f"{'═'*60}\n")

    ok, fail = 0, []

    for i, (drive_id, filename) in enumerate(FILES, 1):
        print(f"[{i:02d}/{len(FILES)}]", end=" ")
        success = download(drive_id, filename)
        if success:
            ok += 1
        else:
            fail.append(filename)
        time.sleep(0.5)  # pause courtoise entre requêtes

    print(f"\n{'═'*60}")
    print(f"  ✓ Téléchargés : {ok}/{len(FILES)}")
    if fail:
        print(f"  ✗ Échecs ({len(fail)}) :")
        for f in fail:
            print(f"      - {f}")
        print("\n  → Les fichiers en échec sont probablement privés dans Drive.")
        print("    Vérifie le partage : Fichier > Partager > 'Toute personne avec le lien'.")
    print(f"{'═'*60}\n")
    print(f"  Fichiers dans : {DEST}")
    print("  Une fois uploadés sur le CDN, donne-moi les URLs et")
    print("  je mettrai à jour audios.html et podcasts.html automatiquement.\n")

if __name__ == "__main__":
    main()
