# Radio — Parole Prophétique FM

Documentation du système de radio automatisée **Parole Prophétique FM** de L'Évangile du Royaume.

- **Station** : `evangile_du_royaume` — diffusion 24h/24, 7j/7
- **Plateforme** : [AzuraCast](https://www.azuracast.com/) (Liquidsoap + Icecast)
- **Écoute** : `https://parole-prophetique-fm.levangileduroyaume.com`
- **Fuseau station** : **UTC** (tous les horaires ci-dessous sont en UTC)

> ⚠️ Objectif spirituel : préserver l'ordre **jingle → message du jour → Bible → louange** et ne jamais interrompre le message du jour. Toute modification doit respecter cet ordre.

---

## 0. État au 17/11/2026 — à relire avant toute intervention

> 🟡 **Le déclencheur externe (cron-job.org) a été muet du 15-16/10 au 19/11/2026** — son token GitHub avait expiré. Remplacé le 19/11 par un token sans expiration ; 1er dispatch de test réussi à 14h22 UTC, rotation et reset à confirmer la nuit suivante. Ce qui suit décrit la période de panne. La rotation
> et le reset de minuit tournent chaque nuit grâce au cron GitHub de secours, mais **3 à 6 h
> en retard** : le reset tombe vers 03h47 au lieu de 00h00, donc hors des 2 min de couverture
> de `000_TRANSITION`. Conséquences mesurées sur 32 nuits : silence réellement audible,
> BLOC_A jamais démarré proprement, message du jour diffusé en trop **31 nuits sur 32**,
> diffusion hors plan multipliée par 16. **Rien n'est encore rétabli** — procédure de remise
> en service : `AUDIT_2026-11-17.md` §5, et fiche de la dépendance au §6 de ce README.
>
> 🔴 **Deux issues d'alerte sont restées ouvertes** (#16 depuis le 10/09, #18 depuis le 17/10).
> Le dédoublonnage par sujet (17/11) empêche désormais une issue d'en bâillonner d'autres,
> mais **ces deux-là doivent être fermées** une fois traitées.
>
> ℹ️ **Ce qui va bien** : jingles à 99,9 % du plan (réglé le 10/09), bouche-trous quasi
> disparus, flux en ligne, reset confirmé 90 nuits sur 90.
>
> 📊 **Chiffres, méthode et commandes de reproduction : `AUDIT_2026-11-17.md`**
> (90 jours de rapports analysés). Ne pas se fier à la mémoire : relancer les commandes du §7
> de l'audit, les chiffres de ce README portent tous leur date de mesure.

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

Depuis le 26/07/2026, ces deux workflows ont **en plus un cron GitHub natif de secours** — voir la note « Filet de sécurité » ci-dessous.

| Workflow | Horaire (UTC) | Déclencheur | Rôle |
|----------|---------------|-------------|------|
| `radio-rotation.yml` | 23h30 | cron-job.org → `workflow_dispatch` **+ cron GitHub de secours** | Rotation : choisit le message **du lendemain** et reconstruit les 4 blocs (pendant que `BLOC_E_LOUANGE_NUIT` est à l'antenne). Commit `chore: rotation du <date>` + `plan_<date>.json` |
| `radio-midnight-reset.yml` | 00h00 | cron-job.org → `workflow_dispatch` **+ cron GitHub de secours** | Redémarre l'AutoDJ, vide la file (les blocs repartent en position 1 : jingle → message), **dédoublonne la file** puis fait 3 contrôles à +40/80/120 s persistés dans `logs/midnight_watch_<date>.log` |
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

> 🛟 **Filet de sécurité sur la rotation et le reset (26/07/2026)** — `cron-job.org` déclenche les deux tâches les plus critiques, donc une panne du service arrête les deux à la fois. C'est arrivé **deux fois** : le 23/06 et surtout du **18 au 21/07 (3 nuits sans rotation)**, où la radio a rediffusé le contenu du 18/07 pendant 3 jours.
>
> Chacun des deux workflows a désormais **un `schedule:` GitHub natif de secours à la même heure**. Le cron GitHub arrive en retard (mesuré sur ce dépôt : **+51 à +129 min**), ce qui est sans conséquence car chaque workflow ne fait quelque chose que si la tâche a réellement été manquée :
>
> - **Rotation** — déjà idempotente : `last_run_date == broadcast_date` → `return` **avant tout appel API**. Un run de secours tardif est donc un no-op strict. Vérifié sur tous les retards jusqu'à +5 h.
> - **Reset de minuit** — *pas* idempotent (il redémarre Liquidsoap à chaque fois). Une **garde** a donc été ajoutée : si `logs/midnight_watch_<date>.log` existe déjà, le run de secours ne fait rien. Sans elle, le cron aurait coupé un titre en pleine diffusion vers 01h **chaque nuit**. La garde ne s'applique qu'aux runs `schedule` : un lancement manuel force toujours le reset.
>
> Quand le secours agit réellement, il ouvre une issue via l'action mutualisée `.github/actions/alerte-declencheur` — label **`declencheur`**, volontairement isolé pour ne bâillonner aucune autre alerte (voir la note ci-dessous). Un `concurrency:` par workflow empêche un run externe et un run de secours de travailler en parallèle.

> 🔇 **Piège majeur — une issue d'alerte ouverte bâillonne les alertes suivantes.** Chaque workflow d'alerte fait `listForRepo({state:'open', labels:…})` et **sort sans rien créer** si une issue portant ces labels existe déjà. Une issue non fermée éteint donc toute la surveillance de son type. Constaté : `#6` (`radio,alerte`) neutralisait **3 workflows** (healthcheck, garde de frontière, capture liquidsoap) et `#8` (`radio,validation`) neutralisait la validation des chemins — **du 20 au 26/07/2026 la radio n'avait plus aucune alerte fonctionnelle**. Récidive constatée le 17/11/2026 : `#16` (`radio,alerte`, ouverte le 10/09) a bâillonné **cinq** workflows pendant **68 jours**, dont « radio hors ligne ».
>
> ✅ **Corrigé le 17/11/2026** : chaque workflow porte un **3e label de sujet** (`flux`, `garde`, `remplissage`, `fondus`, `capture`) et ne cherche plus que les issues de SON sujet. Une issue de playlist ne peut plus masquer une coupure d'antenne. L'alerte `declencheur`, elle, **commente l'issue existante** à chaque occurrence au lieu de se taire — le compteur de nuits mesure la durée de la panne. ➜ **Réflexe inchangé : fermer l'issue dès l'incident traité.**

> ℹ️ **Garde de frontière & ponctualité** — la fenêtre utile vaut la **durée du message** (66 à 156 min), pas 10-25 min : le doublon attend en file pendant toute sa 1re lecture.
>
> - *Mesure du 26/07/2026* : cron GitHub à **+51 à +129 min**, aucun `boundary_watch_*.log` — d'où la conclusion, à l'époque, qu'elle n'avait jamais rien retiré.
> - *Correction du 14/09/2026* : elle **a** fonctionné par intermittence. **9 doublons réellement retirés du 06 au 26/08**, quand le retard du cron était retombé à +17/+37 min ; **zéro en septembre**, quand il est remonté à +110/+312 min.
> - *Mesure du 17/11/2026* : **plus un seul doublon retiré depuis le 26/08** — 270 runs, 100 % `success`, 0 effet. Elle est verte et inutile.
>
> ➜ **Décision à prendre** : lui donner ses déclencheurs cron-job.org à 06h01/12h01/18h01 UTC sur `workflow_dispatch` (seul moyen d'être dans la fenêtre), ou la supprimer. Un workflow vert sans effet est pire qu'absent : il rassure. Minuit reste couvert par le dédoublonnage du reset.

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
| Clé API AzuraCast | **GitHub Secrets** `AZURACAST_API_KEY` (jamais committée) — créée le 28/05/2026, sans expiration ; seule une révocation côté AzuraCast l'invalide. C'est le **seul** secret du dépôt (vérifié le 19/11/2026 : `gh api repos/angorafoot-jojo/site-web/actions/secrets`) |
| Config de rotation **utilisée par les workflows** | `azuracast_rotation_config_option_a.example.json` *(suivi — clé vide, injectée via la variable d'env `AZURACAST_API_KEY`)* |
| Config locale avec clé réelle | `azuracast_rotation_config_option_a.json` / `azuracast_rotation_config.json` *(gitignorées)* |
| État de la rotation | `azuracast_rotation_state.json` *(suivi, persistant)* |
| Musique source locale | `Radio/ParoleProphetiqueFM-musique/` — **2,5 Go, gitignoré, ne jamais committer** (uploader dans AzuraCast) |

### Dépendances tierces

Une dépendance tierce non documentée est une panne qui durera. Celle ci-dessous a
coûté **32 nuits de diffusion dégradée** (15/10 → 17/11/2026) parce que personne ne
savait quel token elle utilisait ni quand il expirait. Toute nouvelle dépendance doit
avoir sa fiche, sur ce gabarit, **avant** d'être mise en service.

#### cron-job.org — déclencheur de la rotation et du reset

| | |
|---|---|
| **Rôle** | Appelle l'API GitHub à l'heure pile pour déclencher `radio-rotation` (23h30 UTC), `radio-midnight-reset` (00h00 UTC) et `radio-boundary-guard` (06h01/12h01/18h01 UTC). Le cron natif de GitHub ne sert que de filet : il arrive avec +110 à +360 min de retard sur ce dépôt. |
| **Tableau de bord** | <https://console.cron-job.org/> — l'historique par job donne le code HTTP de chaque appel, c'est là que se lit une panne de token (`401`). |
| **Compte propriétaire** | Compte Google **personnel de Jonathan** (Gmail), confirmé le 19/11/2026. L'adresse complète n'est volontairement **pas** écrite ici : ce dépôt est public. ⚠️ Ce n'est pas le compte du ministère — une bascule vers un compte partagé reste à envisager, sinon l'accès au déclencheur dépend d'une seule personne. |
| **Secret utilisé** | Un **PAT GitHub fine-grained** (`Actions: Read and write`, dépôt `site-web` uniquement), stocké **dans cron-job.org**, en-tête `Authorization: Bearer …`. ⚠️ Ce token ne vit **pas** dans les GitHub Secrets du dépôt : il n'apparaît donc dans aucun inventaire côté GitHub. Créé sur <https://github.com/settings/personal-access-tokens/new>. |
| **Expiration du token** | **Aucune** — token créé le 19/11/2026 en remplacement du précédent, **qui avait expiré et a causé la panne de 32 nuits**. Supprime le mode de panne « token expiré », mais en crée un autre : un token sans expiration est une autorisation permanente — s'il fuite, l'accès `Actions: Read and write` sur le dépôt l'est aussi. Et il peut **cesser de fonctionner quand même** : révocation manuelle, révocation automatique par GitHub si le secret est détecté dans du code public, changement de politique du compte. ➜ Puisque aucune date ne peut être surveillée, **la détection ci-dessous est le seul garde-fou.** La relire chaque fois qu'on touche à ce token. |
| **Si ça meurt** | La rotation et le reset passent sur le cron GitHub de secours : l'antenne n'est jamais noire, donc **rien ne crie**. Mais le reset tombe vers 03h-05h au lieu de 00h00, hors des 2 min de couverture de `000_TRANSITION` → silence réellement audible, BLOC_A jamais démarré proprement, message du jour diffusé en trop (31 nuits sur 32 lors de la panne d'octobre), diffusion hors plan × 16. Les trois tâches dépendent du **même** service : une panne les emporte ensemble. |
| **Comment le détecter** | 1. `gh run list --workflow radio-rotation.yml --limit 3` → la colonne d'événement doit dire `workflow_dispatch`, **jamais** `schedule`. 2. La ligne **PONCTUALITÉ** en tête du rapport quotidien passe au rouge au-delà de 15 min de retard. 3. Une issue au label `declencheur` s'ouvre, puis se commente chaque nuit (le compteur d'occurrences mesure la durée de la panne). |
| **Comment le réparer** | Recréer les jobs : méthode `POST`, URL `https://api.github.com/repos/angorafoot-jojo/site-web/actions/workflows/<fichier>.yml/dispatches`, corps `{"ref":"main"}`, en-têtes `Accept: application/vnd.github+json`, `Authorization: Bearer <token>`, `X-GitHub-Api-Version: 2022-11-28`, **fuseau du job en UTC**. Réponse normale : `204 No Content`. Tester d'abord sur `radio-boundary-guard.yml`, sans effet à l'antenne. Procédure détaillée : `AUDIT_2026-11-17.md` §5. |
| **Historique des pannes** | **23/06/2026** (1 nuit) · **18→21/07/2026** (3 nuits sans rotation, contenu du 18/07 rediffusé 3 jours) · **15/10→19/11/2026** (35 nuits, masquées par le filet de sécurité — **cause : expiration du token**, confirmée le 19/11 par le propriétaire du compte). Trois pannes en cinq mois sur le maillon le plus critique : l'alternative structurelle — déclencher depuis le serveur AzuraCast, qui doit déjà être debout 24/7 — est à chiffrer (`AUDIT_2026-11-17.md` §5 étape 4). |

> 🔌 **Cloudflare Workers Builds — branchement abandonné, à débrancher (constat du 19/11/2026).**
> Une intégration « Workers Builds » Cloudflare est branchée sur ce dépôt et **échoue sur
> chaque commit humain depuis au moins juillet 2026** — les PR #12 et #15 ont été mergées
> avec ce check rouge. Elle n'apparaît nulle part dans la doc, aucun `wrangler.toml` ni
> fichier Worker n'est versionné, et le build échoue en 0 s : une intégration branchée sur
> un dépôt qui n'a rien à lui donner à construire. Elle reste invisible sur `main` parce que
> les commits des workflows portent `[skip ci]`.
> ➜ **Décision de Jonathan (19/11/2026) : Cloudflare ne sert pas à construire ce site, le
> branchement est à retirer** dans la console Cloudflare (Worker `site-web` → Settings →
> Build → déconnecter le dépôt Git, ou supprimer le Worker s'il est vide).
> ⚠️ **Ne retirer que la connexion Git du Worker.** Si Cloudflare héberge aussi le DNS du
> domaine, ne toucher à aucun enregistrement — en particulier pas au sous-domaine radio
> `parole-prophetique-fm.*` (voir `CLAUDE.md` §18).
> Tant que ce n'est pas fait, un check rouge sans rapport avec le code reste affiché sur
> chaque PR. **C'est un coût réel** : un check en permanence rouge apprend à merger malgré
> le rouge, exactement comme un verdict quotidien en permanence ❌ apprend à ne plus le lire.

> ⬜ **Fiches encore à écrire**, sur le même gabarit : **Backblaze B2** (audio et PDF du site), **AzuraCast / VPS** (la station elle-même), **Sentry** (monitoring des erreurs navigateur), **ElevenLabs** (banque de jingles). Pour chacune : compte propriétaire, secret utilisé et son expiration, ce qui casse, comment le détecter, comment le réparer.

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
| 09/2026 | **Jingles sautés (7,1/jour, 80,3 % de diffusion en août)** — cause racine = **fondus non normalisés**, pas la durée des fichiers | Workflow `radio-jingle-fades.yml` (quotidien, idempotent). **Vérifié le 17/11/2026 : 99,9 % du plan sur 32 jours — clos.** |
| 17/11 | **Le healthcheck ne pouvait pas alerter sur une vraie coupure** : serveur injoignable → `curl` renvoie une chaîne vide → `[ "" -ge 200 ]` plante → étape en `failure` → l'étape d'alerte, conditionnée à `ok == 'false'`, était **sautée**. Il n'alertait que si le serveur répondait une erreur HTTP, donc **seulement quand il était debout** (run `32047601458` du 17/08) | Repli `|| true` + `HTTP_CODE=000`, et condition `!cancelled() && ok != 'true'` : un workflow qui plante alerte au lieu de se taire |
| 17/11 | **Fenêtres « ATTENDU » figées à 23h30-23h40 et 00h00-00h03** : dès que le déclencheur externe est tombé, les mêmes rafales de rotation sont passées hors fenêtre → **~140 faux incidents serveur par jour**, et à l'inverse les bascules sur silence d'un reset tardif restaient classées « attendues » alors qu'elles passaient à l'antenne | Fenêtres calées sur l'heure **réelle** (`generated_at` du plan, 1er contrôle du `midnight_watch`), et `deadair`/`crash` attendus **seulement si le reset est à l'heure**. Ligne **PONCTUALITÉ** au verdict : > 15 min de retard = rouge |

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
