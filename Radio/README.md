# Radio — Parole Prophétique FM

Documentation du système de radio automatisée **Parole Prophétique FM** de L'Évangile du Royaume.

- **Station** : `evangile_du_royaume` — diffusion 24h/24, 7j/7
- **Plateforme** : [AzuraCast](https://www.azuracast.com/) (Liquidsoap + Icecast)
- **Écoute** : `https://parole-prophetique-fm.levangileduroyaume.com`
- **Fuseau station** : **UTC** (tous les horaires ci-dessous sont en UTC)

> ⚠️ Objectif spirituel : préserver l'ordre **jingle → message du jour → Bible → louange** et ne jamais interrompre le message du jour. Toute modification doit respecter cet ordre.

---

## 1. Architecture — 4 blocs + louange de nuit

La journée est découpée en 4 blocs de ~6 h. Chaque bloc rejoue **le même message du jour** mais avec une Bible / musique / jingles différents. Depuis juillet 2026, une 5e playlist **statique** couvre 23h30–minuit pour que **plus aucun bloc ne soit à l'antenne pendant la rotation de 23h30** (sinon la file du bloc reconstruit repartait en position 1 et diffusait le message du lendemain en « teaser » coupé à minuit).

| Playlist | Plage horaire (UTC) | ID API | Reconstruite chaque jour ? |
|----------|---------------------|--------|----------------------------|
| `000_TRANSITION` | 00h00 – 00h02 (jingle long ~2 min, comble le silence du restart) | 34 | non |
| `BLOC_A_SERIE_DU_JOUR` | 00h02 – 05h59 | 30 | oui |
| `BLOC_B_SERIE_DU_JOUR` | 06h00 – 11h59 | 31 | oui |
| `BLOC_C_SERIE_DU_JOUR` | 12h00 – 17h59 | 32 | oui |
| `BLOC_D_SERIE_DU_JOUR` | 18h00 – **23h29** (construit à 5h30 via `BLOCK_SLOT_SECONDS`) | 33 | oui |
| `BLOC_E_LOUANGE_NUIT` | 23h30 – 23h59 (louange en aléatoire) | 35 | **non — statique, jamais touchée par la rotation** |

**Structure d'un bloc** : `jingle → message du jour → jingle → Bible ~60min → jingle → musique ~60min → jingle → Bible ~30min → …`

### Garde-fous intégrés à la construction des blocs

Règles apprises en production (voir §6) et codées dans `azuracast_rotation_4_blocs.py` :

- **Rotation en 2 phases** : les 4 blocs sont **vidés d'abord, puis importés/réordonnés** — l'endpoint `PUT /file/{id}` d'AzuraCast détruit et ré-appende les lignes du fichier dans ses *autres* playlists, donc un clear bloc-par-bloc déplaçait les jingles partagés en fin de playlist.
- **`MIN_JINGLE_SECONDS = 6`** : les jingles plus courts sont écartés (l'AutoDJ échoue sur les fichiers ultra-courts et ressert un titre déjà en file — souvent le message, rejoué 2×). Le seuil fiable mesuré est **9 s** ; le pool AzuraCast a été nettoyé à la source (banque de jingles ElevenLabs ≥9 s, juillet 2026).
- **`MIN_MUSIC_SECONDS = 60`** : filtre du pool musique (des jingles importés par erreur avec les cantiques étaient sélectionnés comme slots musique). La Bible n'est **pas** filtrée (Psaume 117 = 16 s légitime).
- **Exclusion des fichiers orphelins** : `get_playlist_files()` exclut explicitement les fichiers dont `playlists=[]` (l'API `GET /files?playlist=X` ignore le paramètre et renvoie toute la médiathèque — toujours filtrer côté client).
- **Plan quotidien archivé** : chaque rotation écrit l'ordre explicite complet de la journée dans `Radio/plans/plan_<date>.json` — c'est la référence « PRÉVU » du rapport de diffusion.

### Playlists sources (bibliothèques — ne PAS activer en diffusion directe)

| Playlist | ID API | Contenu |
|----------|--------|---------|
| `001_LA_MUSIQUE` | 22 | Louange / cantiques |
| `002_BIBLE AUDIO` | 23 | Bible audio |
| `014_Jingles` | 29 | Jingles (banque ElevenLabs ≥9 s depuis juillet 2026) |
| `015_REMPLISSAGE` | *auto* | **Filet de secours** — jingles + chapitres bibliques de 9 à 90 s, en **rotation générale (aucun créneau)**. Les 4 blocs + `BLOC_E` + `000_TRANSITION` couvrant 100 % de la journée, elle ne peut jouer que lorsqu'aucune playlist planifiée ne fournit de titre : uniquement les résidus de fin de bloc. Maintenue par `setup_filler_playlist.py` |
| `003`–`013` | — | Séries d'enseignements (voir plus bas) |

### Séries d'enseignement

| # | Nom | Épisodes |
|---|-----|----------|
| 003 | AM Chandelier d'or | 5 |
| 004 | Au milieu des Chandeliers | 6 |
| 005 | Conquête du royaume | 5 |
| 006 | Nous faire part | 5 |
| 007 | Aux pieds du Seigneur | 7 |
| 008 | Parole qui éclaire | 10 |
| 009 | Le pardon | 8 |
| 010 | 2020 (aud 20200824) | 2 |
| 013 | Combat | 6 |
| 012 | Autres Émissions | *exclu de la rotation auto* |

---

## 2. Automatisation (GitHub Actions)

Tous les horaires sont en **UTC**. La rotation et le reset de minuit sont déclenchés **de l'extérieur par [cron-job.org](https://cron-job.org)** via `workflow_dispatch`, car le cron natif de GitHub Actions subit un retard de 2 min à 5 h (file d'attente partagée).

| Workflow | Horaire (UTC) | Déclencheur | Rôle |
|----------|---------------|-------------|------|
| `radio-rotation.yml` | 23h30 | cron-job.org → `workflow_dispatch` | Rotation : choisit le message **du lendemain** et reconstruit les 4 blocs (pendant que `BLOC_E_LOUANGE_NUIT` est à l'antenne). Commit `chore: rotation du <date>` + `plan_<date>.json` |
| `radio-midnight-reset.yml` | 00h00 | cron-job.org → `workflow_dispatch` | Redémarre l'AutoDJ, vide la file (les blocs repartent en position 1 : jingle → message), **dédoublonne la file** puis fait 3 contrôles à +40/80/120 s persistés dans `logs/midnight_watch_<date>.log` |
| `radio-boundary-guard.yml` | 06h/12h/18h | cron GitHub (+ cron-job.org 06h01/12h01/18h01 recommandé, voir note) | **Garde de frontière de bloc** : retire de la file les doublons du message qui apparaissent quand le bloc sortant s'épuise avant la frontière. Lecture seule + DELETE, no-op silencieux sans doublon ; commit `logs/boundary_watch_*.log` seulement si un doublon a été retiré |
| `radio-healthcheck.yml` | toutes les 15 min | cron GitHub | Vérifie que le flux diffuse |
| `radio-liquidsoap-capture.yml` | toutes les heures (h+17) | cron GitHub | Capture les lignes d'intérêt du `liquidsoap.log` (erreurs, échecs, titres préparés) dans `logs/liquidsoap_events_<date>.log` — le log serveur est un tampon glissant d'~24 h, sans capture les causes des anomalies disparaissent avant le rapport |
| `radio-playback-report.yml` | 01h00 | cron GitHub | Génère le rapport de diffusion de la veille (`logs/diffusion_<date>.log`) |
| `radio-jingle-fades.yml` | 10h00 | cron GitHub | **Normalisation des fondus de jingles** : remet `fade_in`/`fade_out`/`fade_overlap` à 0 sur tout le dossier `Jingle/`. Un fichier fraîchement uploadé hérite du crossfade station (~4 s perdues) et devient injouable par l'AutoDJ — ce workflow répare cette dérive automatiquement après chaque import. Idempotent : no-op quand le pool est conforme |
| `radio-filler-playlist.yml` | 10h15 | cron GitHub | **Playlist de secours** `015_REMPLISSAGE` (jingles + chapitres bibliques ≤ 90 s) en rotation générale : comble les résidus de fin de bloc à la place du « AzuraCast is Live! » d'AzuraCast. Déclenchement manuel avec modes `dry-run` / `apply` / `disable` |
| `radio-validate-paths.yml` | 12h00 | cron GitHub | Vérifie que chaque chemin de la config existe dans la médiathèque |
| `radio-test-playlists.yml` | manuel | `workflow_dispatch` | Test : vérifie les playlists via l'API |
| `radio-test-liquidsoap-log.yml` | manuel | `workflow_dispatch` | Test : liste les logs serveur disponibles et inspecte le contenu brut du `liquidsoap.log` |
| `radio-test-restart.yml` | manuel | `workflow_dispatch` | Test : restart AutoDJ + vérification du pointeur |

> ℹ️ **Garde de frontière & ponctualité** : le doublon attend en file pendant toute la 1re lecture du message (10–25 min), donc le retard typique du cron GitHub (2–10 min) est toléré. Pour une ponctualité garantie, ajouter des déclencheurs cron-job.org à 06h01/12h01/18h01 UTC sur `workflow_dispatch` (comme pour la rotation et le reset). Minuit est déjà couvert par le dédoublonnage du reset.

> ℹ️ **Ce qui planifie une playlist AzuraCast, c'est la présence de `schedule_items` — pas son `type`.** Vérifié le 10/09/2026 sur le dump complet de `000_TRANSITION` : `type: default` **avec** un créneau 00h00-00h02, et elle diffuse correctement depuis des mois. `015_REMPLISSAGE` est donc bien en rotation générale parce qu'elle n'a **aucun** créneau, pas parce que son type vaut `default`. L'API de cette station ne renvoie par ailleurs **aucun champ `include_in_automation`** (qui désigne la fonction « Automated Assignment », sans rapport avec la diffusion).
>
> ✅ **`radio-test-playlists.yml` — corrigé le 10/09/2026.** Ce workflow apparaissait « failed » en 0 s à **chaque push** depuis le 24/06, et c'était documenté ici comme un « run fantôme créé par GitHub » : diagnostic erroné. Le fichier était **invalide** — le script Python embarqué avait été collé en colonne 1 alors que le bloc `run: |` est indenté de 10 espaces, ce qui terminait le scalaire et faisait échouer l'analyse YAML (`could not find expected ':'`). Symptôme révélateur : GitHub affichait ce workflow par son chemin de fichier au lieu de son `name:`, faute de pouvoir le lire. Le Python est désormais indenté au niveau du bloc — YAML retire l'indentation commune, Python reçoit bien son code en colonne 0. Deux bugs de son propre script, restés invisibles faute de pouvoir s'exécuter, ont été corrigés dans la foulée : `start_time`/`end_time` sont des **entiers** HHMM (`0`, `2`, `1200`) et non des chaînes, et l'analyse criait au « risque de diffusion hors créneau » sur toute playlist de type `default`, y compris `000_TRANSITION` qui est saine.
>
> Une alerte permanente n'est pas une alerte : c'est le même piège que le faux positif du healthcheck (27/07) et que le `❌` quotidien du moniteur (10/09). Un échec dans l'onglet Actions doit redevenir un signal.

---

## 3. Scripts Python

Tous dans `Radio/`. Dépendance unique : `requests` (`pip install -r requirements.txt`).

| Script | Rôle |
|--------|------|
| `azuracast_rotation_4_blocs.py` | **Script principal de rotation** — sélectionne le message du jour, applique les garde-fous (§1) et remplit les 4 blocs ; écrit `plans/plan_<date>.json` |
| `restart_autodj.py` | Reset de minuit : restart AutoDJ + clear de la file + **dédoublonnage** (supprime les entrées de file identiques au titre à l'antenne, même non adjacentes) + 3 contrôles persistés. Mode **`--watch-only`** = garde de frontière (surveillance/dédoublonnage seuls, aucun restart) |
| `playback_report.py` | Rapport de diffusion quotidien. En tête, section **MONITEUR** : verdict à 3 niveaux (`✅ RAS` · `⚠️ suites connues du reset/rotation` · `❌ incident`), les signatures des fenêtres planifiées (`ROTATION_WINDOW`, `MIDNIGHT_RESET_WINDOW`) étant affichées sur une ligne **ATTENDU** hors verdict. Puis synthèse et **corrélation des 3 rapports + plan** en une seule vue (anomalies de diffusion ↔ incidents serveur `liquidsoap_events` ↔ actions de reset/garde `midnight/boundary_watch`), pour ne plus chercher la cause dans 3 fichiers. Puis le détail : RÉEL vs PRÉVU (plan du jour), section **CONTRÔLES APPROFONDIS** (diffusions du message + détection « DOUBLE RAPPROCHÉ », jingles par bloc, hors fenêtre, bouche-trous, couverture début/fin de journée), paliers de gravité. Matching du message par titre **ou par durée ±2 s** (les tags ID3 divergent des étiquettes du plan) ; les entrées du lendemain (fetch +15 min pour mesurer le dernier titre) sont filtrées partout |
| `capture_liquidsoap_log.py` | Capture horaire des événements du `liquidsoap.log` serveur (erreurs, avertissements niveau ≤2, « Fetch failed », `Prepared "…"`, bascules de source) vers `logs/liquidsoap_events_<date>.log`. Idempotent via `liquidsoap_capture_state.json` (position + dernier horodatage archivé) |
| `validate_paths.py` | Vérifie que chaque chemin de la config existe dans la médiathèque + cohérence des créneaux planifiés (`EXPECTED_SLOTS`) |
| `retitle_bible_files.py` | Réécrit les métadonnées (titre + artiste) des fichiers bibliques |
| `setup_filler_playlist.py` | Maintient `015_REMPLISSAGE` (`--apply`, dry-run par défaut, `--disable` pour le rollback). **N'ajoute que par import M3U** — jamais via `PUT /file/{id}`, qui réordonnerait les blocs (§5) |
| `test_setup_filler_playlist.py` | Tests de la sélection, de l'idempotence de l'import et des réglages de la playlist |
| `set_jingle_fades.py` | Désactive le crossfade sur les jingles (`--apply`, dry-run par défaut). **À rejouer après chaque import de jingles** — automatisé par `radio-jingle-fades.yml`. Signale aussi la durée utile de chaque fichier (durée − fondus) et alerte sous 9 s |
| `test_set_jingle_fades.py` | Tests de la sélection des jingles à normaliser (idempotence, périmètre, durée utile) |
| `test_azuracast_rotation.py` | Tests de la logique de rotation |
| `test_restart_autodj.py` | Tests du reset/dédoublonnage/garde de frontière |
| `test_playback_report.py` | Tests du rapport de diffusion |
| `test_capture_liquidsoap_log.py` | Tests du filtrage/dédoublonnage de la capture Liquidsoap |
| `azuracast_rotation_option_a_final_v3.py` | **Obsolète** (ancienne version mono-script, ex-LaunchAgent local déchargé le 02/07) — conservé pour référence, ne pas utiliser |

```bash
cd Radio && python3 -m pytest   # lancer toute la suite de tests
```

### Lancer la rotation en local

```bash
cd Radio
pip install -r requirements.txt

# Test à blanc — ne modifie PAS AzuraCast
python3 azuracast_rotation_4_blocs.py --dry-run --force-advance

# Exécution forcée (avance d'un cran)
python3 azuracast_rotation_4_blocs.py --force-advance

# Exécution quotidienne normale
python3 azuracast_rotation_4_blocs.py
```

`azuracast_rotation_state.json` mémorise la position de la rotation : **il doit rester persistant** entre les exécutions (committé dans le repo / restauré dans le workflow).

---

## 4. Fichiers générés et persistés

| Fichier / dossier | Écrit par | Suivi git |
|-------------------|-----------|-----------|
| `plans/plan_<date>.json` | rotation (23h30, pour le lendemain) | ✅ committé — référence « PRÉVU » du rapport |
| `logs/diffusion_<date>.log` | `playback_report.py` (01h00) | ✅ committé |
| `logs/midnight_watch_<date>.log` | reset de minuit (3 instantanés JSON Lines à +40/80/120 s) | ✅ committé |
| `logs/boundary_watch_*.log` | garde de frontière (seulement si un doublon a été retiré) | ✅ committé |
| `logs/liquidsoap_events_<date>.log` | capture Liquidsoap (toutes les heures) | ✅ committé — matière première des « causes probables » |
| `liquidsoap_capture_state.json` | capture Liquidsoap (position de lecture + dernier horodatage) | ✅ committé, **persistant** |
| `azuracast_rotation_state.json` | rotation (position dans le cycle des séries) | ✅ committé, **persistant** |
| `azuracast_4_blocs_debug.json`, `azuracast_cycle_debug.json` | rotation (debug de chaque run) | ❌ gitignorés |

---

## 5. API AzuraCast

- **Station ID** : `1`
- **Auth** : header `Authorization: Bearer <CLÉ_API>`
- **La clé API vit UNIQUEMENT dans les GitHub Secrets** (`AZURACAST_API_KEY`) — jamais dans le code ni dans un fichier committé.

```bash
BASE="https://parole-prophetique-fm.levangileduroyaume.com/api/station/1"

# Lister les playlists
curl -H "Authorization: Bearer $CLE" "$BASE/playlists"

# Fichiers d'une playlist (ex. musique = 22)
curl -H "Authorization: Bearer $CLE" "$BASE/files?playlist=22&limit=2"
```

Champs utiles renvoyés : `id`, `path`, `title`, `length` (secondes), `length_text`, `playlists`.

### Pièges API connus (appris en production)

- `GET /files?playlist=X` **ignore le paramètre** et renvoie toute la médiathèque → toujours filtrer côté client sur `row['playlists']`.
- `PUT /file/{id}` avec une liste de `playlists` **détruit puis recrée** les lignes du fichier dans ses autres playlists (ré-appendées en fin) → d'où la rotation en 2 phases.
- `POST /playlists` **ignore `schedule_items`** → toujours re-`PUT` la planification après création.
- La réponse de `GET /queue` n'expose pas d'id de ligne → cibler les DELETE via `links.self`.
- Accents : macOS envoie les noms de fichiers en **NFD**, AzuraCast attend du **NFC** → normaliser avant upload.

---

## 6. Configuration & secrets

| Élément | Emplacement |
|---------|-------------|
| Clé API AzuraCast | **GitHub Secrets** `AZURACAST_API_KEY` (jamais committée) |
| Config de rotation **utilisée par les workflows** | `azuracast_rotation_config_option_a.example.json` *(suivi — clé vide, injectée via la variable d'env `AZURACAST_API_KEY`)* |
| Config locale avec clé réelle | `azuracast_rotation_config_option_a.json` / `azuracast_rotation_config.json` *(gitignorées)* |
| État de la rotation | `azuracast_rotation_state.json` *(suivi, persistant)* |
| Musique source locale | `Radio/ParoleProphetiqueFM-musique/` — **2,5 Go, gitignoré, ne jamais committer** (uploader dans AzuraCast) |

---

## 7. Historique des incidents résolus (résumé)

Pour comprendre *pourquoi* le code est comme il est :

| Date | Incident | Correctif |
|------|----------|-----------|
| 06/2026 | Bible désordonnée / chapitres rejoués | Normalisation NFC des chemins à l'upload |
| 02/07 | Jingles « sautés » à ~85 % — en fait **déplacés** en fin de playlist par les clears successifs | Rotation en 2 phases (vider les 4 blocs, puis importer) |
| 02/07 | Message du lendemain « teasé » à ~23h47 puis coupé à minuit | `BLOC_D` s'arrête à 23h29, `BLOC_E_LOUANGE_NUIT` statique couvre 23h30–minuit |
| 02/07 | Message joué 2× d'affilée à minuit | Dédoublonnage de la file dans le reset de minuit |
| 06/07 | Messages rejoués 2× en journée — cause racine = **jingles de 1–5 s** que l'AutoDJ échoue à lancer | `MIN_JINGLE_SECONDS=6` + remplacement du pool par des jingles ElevenLabs ≥9 s (09/07) |
| 08/07 | Jingles parasites dans le pool musique | `MIN_MUSIC_SECONDS=60` |
| 08/07 | Fichiers orphelins (`playlists=[]`) réinjectés dans la rotation | Exclusion explicite dans `get_playlist_files()` |
| 12/07 | Rapport : message compté 0/4 à tort + jingles surcomptés | Matching par durée ±2 s + filtrage des entrées du lendemain |
| 13/07 | Doublon du message aux frontières 06h/12h/18h (double remplissage de file quand le bloc sortant s'épuise avant la frontière) | Dédoublonnage étendu (titre à l'antenne, même non adjacent) + workflow `radio-boundary-guard.yml` |
| 09/2026 | **Jingles sautés (7,1/jour, 80,3 % de diffusion en août)** — cause racine = **fondus non normalisés**, pas la durée des fichiers | Workflow `radio-jingle-fades.yml` (quotidien, idempotent) |

#### Jingles sautés — cause racine (analyse des 31 jours d'août 2026)

Le chantier ouvert depuis juillet est clos. Sur août : **896 jingles diffusés sur 1 116 prévus (80,3 %)**, soit 220 perdus, répartis uniformément sur les 4 blocs. Le saut ne touchait quasiment que les jingles (163 des 165 items « prévu non joué »).

La corrélation apparente avec la durée du fichier était en réalité une corrélation avec la **durée utile à l'antenne = durée déclarée − fondus** :

| Lot | Normalisé le 12/06 ? | Durée | Taux de saut |
|-----|----------------------|-------|--------------|
| `jingle_id_station_01/02` | ✅ oui | 9 s | **3–6 %** |
| `jingle_id_station_03` | ✅ oui | 12 s | **0 %** |
| `jingle_avant_bible_08` | ❌ non | 9 s | **31 %** |
| `jingle_avant_message_03` | ❌ non | 9 s | **45 %** |
| `jingle_avant_bible_06`, `avant_louange_06` | ❌ non | 10 s | **21–23 %** |
| `jingle_avant_bible_07`, `avant_louange_07` | ❌ non | 13 s | **2–6 %** |

À **durée identique (9 s)**, un jingle normalisé saute 3 % et un jingle non normalisé 31 à 45 %. Le crossfade station (2 s de chaque côté) ampute ~4 s : un fichier de 9 s ne dure plus que 5 s à l'antenne, sous le seuil où l'AutoDJ échoue à le lancer.

**Pourquoi la dérive** : `set_jingle_fades.py` n'avait été lancé **qu'une seule fois, à la main, le 12/06/2026** (commit `52b717b`, « les 40 jingles »), et aucun workflow ne le rejouait. La banque ElevenLabs importée les **09-10/07/2026** — celle qui compose tout le pool actuel — n'a donc jamais été normalisée. Les seuls jingles épargnés sont ceux présents dès le 04/06 (`id_station_01/02/03`), d'où leur taux de saut quasi nul.

**Confirmé en production le 10/09/2026** (dry-run de `radio-jingle-fades.yml`) : sur 49 fichiers du dossier `Jingle/`, **exactement 9 avaient `fade_in`/`fade_out`/`fade_overlap` à `null`** — soit précisément le lot de juillet (`avant_message_03/04/05`, `avant_bible_06/07/08`, `avant_louange_05/06/07`). Les 40 autres étaient déjà à 0 depuis le 12/06. Durées utiles estimées et taux de saut d'août, dans le même ordre :

| Durée utile (durée − crossfade) | Jingles concernés | Saut mesuré en août |
|--------------------------------|-------------------|---------------------|
| ~5 s | `avant_message_03`, `avant_bible_08` | 31–45 % |
| ~6 s | `avant_message_04`, `avant_bible_06`, `avant_louange_06` | 19–23 % |
| ~7 s | `avant_message_05`, `avant_louange_05` | 12–13 % |
| ~9 s | `avant_bible_07`, `avant_louange_07` | 2–6 % |

> ⚠️ **Règle à retenir** : tout import de jingles doit être suivi d'une normalisation des fondus. C'est désormais automatique (`radio-jingle-fades.yml`, 10h UTC), mais après un import manuel on peut la déclencher tout de suite depuis Actions plutôt que d'attendre le lendemain.

### Chantier ouvert

- **Corrélation des « PRÉVU NON JOUÉ »** : `playback_report.py` corrèle les anomalies **horodatées** (coupure, trou, double message) avec l'incident serveur le plus proche (fait le 22/07/2026), mais pas encore les items sautés du plan, qui n'ont pas d'heure propre — il faudrait les rattacher aux événements serveur de leur fenêtre de bloc.
> ✅ **Assèchement de fin de bloc — traité le 10/09/2026.** 28 fois sur août-septembre, le dernier titre d'un bloc s'est terminé avant la fin de sa fenêtre et Liquidsoap a diffusé `error.mp3` (« AzuraCast is Live! ») pendant 1 à 55 s (médiane 30 s), toujours interrompu pile à la bascule. C'est aussi la cause des 3 doubles messages des 3, 4 et 5 août.
>
> **Mécanisme** : AzuraCast lance tout ce qui *tient* dans le temps restant — dans 17 cas sur 28, le dernier titre joué est un jingle de ~10 s — puis refuse l'item suivant du plan, trop long. Ce n'est donc ni un manque de contenu (les blocs débordent de 12 à 40 min) ni un défaut de la rotation : il manque un item **court** à jouer dans le résidu.
>
> **Correctif** : la playlist `015_REMPLISSAGE` (jingles + chapitres bibliques de 9 à 90 s) en **rotation générale**, maintenue par `radio-filler-playlist.yml`. Reste à confirmer en production sur le premier résidu observé — voir la note ci-dessous.
> ✅ **Bruit du monitoring — corrigé le 10/09/2026.** Le rapport titrait `❌ incident détecté` 31 jours sur 31 : 99 % des événements comptés venaient de la rotation (23h30-23h40) et du reset de minuit (00h00-00h03), et les 26 anomalies de diffusion d'août-septembre étaient toutes le même titre tronqué par le redémarrage. Ces signatures planifiées sont désormais classées **ATTENDU** — affichées, mais hors verdict. Sur les 41 jours rejoués : **18 passent au vert**, les 23 restants sont rouges pour un assèchement de frontière réel (voir ci-dessus). L'alerte de doublon de file du reset, qui se déclenchait 29 nuits sur 41 sans qu'aucune double diffusion ne suive, ignore maintenant les jingles : **0 faux positif**, et les 9 détections réelles de la garde de frontière sont conservées. Une diffusion du message en trop compte enfin dans le verdict même sans « double rapproché » (cas du 01/09 : 5 diffusions pour 4, espacées de plus de 15 min, que le verdict ne voyait pas).

---

## 8. En cas de problème

1. **Le flux est muet** → vérifier le workflow `radio-healthcheck` (Actions) ; relancer `radio-midnight-reset` manuellement.
2. **Le message du jour passe 2× d'affilée** → relancer `radio-boundary-guard` (ou `restart_autodj.py --watch-only` en local) ; vérifier `logs/boundary_watch_*.log` et `logs/midnight_watch_*.log`.
3. **Mauvais message diffusé / blocs désynchronisés** → relancer `radio-rotation` puis `radio-midnight-reset`.
4. **Un fichier ne joue pas** → lancer `validate_paths.py` (ou le workflow `radio-validate-paths`) pour repérer un chemin manquant.
5. **Analyser une journée de diffusion** → lire `logs/diffusion_<date>.log` : la section **MONITEUR** en tête synthétise et corrèle les 3 rapports + le plan (état du jour, incidents serveur, reset/garde, cause probable de chaque anomalie). Le détail titre par titre suit en dessous. Workflow `radio-playback-report`, relançable manuellement avec une date en entrée.
