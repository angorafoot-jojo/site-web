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
| `radio-boundary-guard.yml` | **manuel uniquement** (cron GitHub retiré le 27/07/2026, voir note) | `workflow_dispatch` | **Garde de frontière de bloc** : retire de la file les doublons du message qui apparaissent quand le bloc sortant s'épuise avant la frontière. Lecture seule + DELETE, no-op silencieux sans doublon ; commit `logs/boundary_watch_*.log` seulement si un doublon a été retiré |
| `radio-healthcheck.yml` | toutes les 15 min | cron GitHub | Vérifie que le flux diffuse |
| `radio-liquidsoap-capture.yml` | toutes les heures (h+17) | cron GitHub | Capture les lignes d'intérêt du `liquidsoap.log` (erreurs, échecs, titres préparés) dans `logs/liquidsoap_events_<date>.log` — le log serveur est un tampon glissant d'~24 h, sans capture les causes des anomalies disparaissent avant le rapport |
| `radio-playback-report.yml` | 01h00 | cron GitHub | Génère le rapport de diffusion de la veille (`logs/diffusion_<date>.log`) |
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

> 🔇 **Piège majeur — une issue d'alerte ouverte bâillonne les alertes suivantes.** Chaque workflow d'alerte fait `listForRepo({state:'open', labels:…})` et **sort sans rien créer** si une issue portant ces labels existe déjà. Une issue non fermée éteint donc toute la surveillance de son type. Constaté : `#6` (`radio,alerte`) neutralisait **3 workflows** (healthcheck, garde de frontière, capture liquidsoap) et `#8` (`radio,validation`) neutralisait la validation des chemins — **du 20 au 26/07/2026 la radio n'avait plus aucune alerte fonctionnelle**. ➜ **Réflexe : fermer l'issue dès l'incident traité.**

> ⚠️ **Garde de frontière — cron GitHub RETIRÉ le 27/07/2026 : il ne pouvait pas fonctionner.** Le doublon n'attend en file que pendant la 1re lecture du message, soit une **fenêtre utile de 10–25 min**. Mesure sur 18 runs consécutifs : le cron GitHub arrive avec **+51 à +129 min de retard, jamais moins de 51 min** — donc toujours hors fenêtre.
>
> Preuve par l'absence : **aucun `logs/boundary_watch_*.log` n'a jamais été créé** → la garde n'a jamais retiré un seul doublon depuis sa mise en place. Contre-preuve directe le 25/07 : doublons à 06:09:52 et 12:09:52 (message diffusé 6× pour 4 prévues), garde passée à 07:49 et 12:59.
>
> Le workflow reste **déclenchable à la main** et redevient efficace dès qu'on lui ajoute des déclencheurs **cron-job.org à 06h01/12h01/18h01 UTC** sur `workflow_dispatch`. Contrairement à la rotation et au reset, une panne de cron-job.org ne ferait ici que **désactiver** la garde, sans dégât en cascade : ce n'est donc pas un point de défaillance critique. Minuit est déjà couvert par le dédoublonnage du reset.
>
> ➜ La cause racine reste à traiter, voir « Chantier ouvert » (§7).

> ⚠️ **Faux échec connu** : `radio-test-playlists.yml` apparaît « failed » à chaque push sur `main` (GitHub crée un run fantôme malgré `on: workflow_dispatch` seul). Connu depuis le 24/06, gardé volontairement (outil de diagnostic manuel), zéro impact — ne pas traiter comme une régression.

---

## 3. Scripts Python

Tous dans `Radio/`. Dépendance unique : `requests` (`pip install -r requirements.txt`).

| Script | Rôle |
|--------|------|
| `azuracast_rotation_4_blocs.py` | **Script principal de rotation** — sélectionne le message du jour, applique les garde-fous (§1) et remplit les 4 blocs ; écrit `plans/plan_<date>.json` |
| `restart_autodj.py` | Reset de minuit : restart AutoDJ + clear de la file + **dédoublonnage** (supprime les entrées de file identiques au titre à l'antenne, même non adjacentes) + 3 contrôles persistés. Mode **`--watch-only`** = garde de frontière (surveillance/dédoublonnage seuls, aucun restart) |
| `playback_report.py` | Rapport de diffusion quotidien. En tête, section **MONITEUR** : synthèse et **corrélation des 3 rapports + plan** en une seule vue (anomalies de diffusion ↔ incidents serveur `liquidsoap_events` ↔ actions de reset/garde `midnight/boundary_watch`), pour ne plus chercher la cause dans 3 fichiers. Puis le détail : RÉEL vs PRÉVU (plan du jour), section **CONTRÔLES APPROFONDIS** (diffusions du message + détection « DOUBLE RAPPROCHÉ », jingles par bloc, hors fenêtre, bouche-trous, couverture début/fin de journée), paliers de gravité. Matching du message par titre **ou par durée ±2 s** (les tags ID3 divergent des étiquettes du plan) ; les entrées du lendemain (fetch +15 min pour mesurer le dernier titre) sont filtrées partout |
| `capture_liquidsoap_log.py` | Capture horaire des événements du `liquidsoap.log` serveur (erreurs, avertissements niveau ≤2, « Fetch failed », `Prepared "…"`, bascules de source) vers `logs/liquidsoap_events_<date>.log`. Idempotent via `liquidsoap_capture_state.json` (position + dernier horodatage archivé) |
| `validate_paths.py` | Vérifie que chaque chemin de la config existe dans la médiathèque + cohérence des créneaux planifiés (`EXPECTED_SLOTS`) |
| `retitle_bible_files.py` | Réécrit les métadonnées (titre + artiste) des fichiers bibliques |
| `set_jingle_fades.py` | Désactive le crossfade sur les jingles |
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

### Chantier ouvert

- **Jingles réellement sautés (5–14/jour)** : fichiers de 8–13 s qui existent et jouent bien à d'autres heures, sautés éparpillés en milieu de bloc. Piste : réglage *duplicate prevention* d'AzuraCast ou comportement Liquidsoap sur fichiers courts. Les logs Liquidsoap nécessaires sont archivés depuis le 18/07/2026 par `radio-liquidsoap-capture.yml` (le log serveur est bien exposé par l'API — `GET /station/1/log/liquidsoap_log` — mais c'est un tampon glissant d'~24 h, d'où la capture horaire).
  - **Fait (22/07/2026)** : la section **MONITEUR** de `playback_report.py` corrèle désormais chaque anomalie **horodatée** de diffusion (coupure, trou, double message) avec l'incident serveur le plus proche (crash, échec réseau, silence, saut) et l'état du reset/garde. Une coupure et sa cause serveur s'affichent côte à côte, plus besoin d'ouvrir les 3 fichiers.
  - **Reste** : corréler aussi les items **« PRÉVU NON JOUÉ »** du plan (jingles sautés sans horodatage propre) avec les événements serveur de leur fenêtre de bloc — la corrélation actuelle porte sur les anomalies qui ont une heure précise.

- **Doublon du message aux frontières — cause immédiate identifiée le 27/07/2026, pas encore corrigée.** Le workflow `radio-boundary-guard.yml` ne traitait que le symptôme, et son cron GitHub était trop tardif pour même y parvenir (voir la note du §2). Mesure sur 9 jours de rapports (15→26/07) :

  | Jour | Message | Micro-trou juste avant une frontière |
  |------|---------|--------------------------------------|
  | 15/07 | **5**/4 | `17:59:46` |
  | 16→18, 22, 23, 26/07 | 4/4 ✅ | — |
  | 24/07 | **5**/4 | `17:59:24` |
  | 25/07 | **6**/4 | `05:59:59` · `11:59:37` |

  **Corrélation 4/4, zéro faux positif, zéro cas manqué** : chaque diffusion en trop est précédée d'un bouche-trou de 6 à 28 s (`AzuraCast is Live!`) dans la dernière minute avant une frontière, et tous les jours sans micro-trou sont à 4/4 exact. Fréquence : ~0,4 diffusion en trop par jour, sur 1 jour sur 3.

  Mécanisme retenu : le bloc sortant laisse un micro-silence avant la frontière → le *fallback* Liquidsoap prend l'antenne → la file du bloc entrant se remplit **deux fois** (`[jingle, message] × 2`) → le message part 2× d'affilée ~10 min après la frontière.

  **Pistes à explorer, par ordre de robustesse :**
  1. **Supprimer le micro-trou** (vraie correction) : garantir qu'un titre du bloc sortant couvre la frontière. À rapprocher de la PR #7 (budget global par bloc).
  2. **`duplicate_prevention_time_range` d'AzuraCast** : vaut **5** dans `backend_config` (vérifié via `GET /api/admin/station/1` le 27/07). Si l'unité est la minute, une reprise à +9 min passe entre les mailles, alors que les rediffusions **légitimes** du message sont à 6 h d'intervalle — une valeur plus élevée (30–60) bloquerait le doublon sans toucher au plan. ⚠️ **À vérifier avant de changer quoi que ce soit** : unité réelle du réglage, et si la prévention s'applique à une file **déjà construite** (le doublon vient d'un double remplissage, pas d'une sélection de titre).
  3. **Brancher la garde sur cron-job.org** (06h01/12h01/18h01 UTC) : corrigerait les 4 cas mesurés, mais reste un pansement sur le symptôme.

---

## 8. En cas de problème

1. **Le flux est muet** → vérifier le workflow `radio-healthcheck` (Actions) ; relancer `radio-midnight-reset` manuellement.
2. **Le message du jour passe 2× d'affilée** → lancer `radio-boundary-guard` **à la main** (il n'a plus de cron, voir §2) **dans les 10 min suivant la frontière**, sinon le doublon a déjà joué et l'intervention est inutile ; ou `restart_autodj.py --watch-only` en local. Vérifier `logs/boundary_watch_*.log` et `logs/midnight_watch_*.log`. Cause immédiate connue : micro-trou avant la frontière — voir « Chantier ouvert » (§7).
3. **Mauvais message diffusé / blocs désynchronisés** → relancer `radio-rotation` puis `radio-midnight-reset`.
4. **Un fichier ne joue pas** → lancer `validate_paths.py` (ou le workflow `radio-validate-paths`) pour repérer un chemin manquant.
5. **Analyser une journée de diffusion** → lire `logs/diffusion_<date>.log` : la section **MONITEUR** en tête synthétise et corrèle les 3 rapports + le plan (état du jour, incidents serveur, reset/garde, cause probable de chaque anomalie). Le détail titre par titre suit en dessous. Workflow `radio-playback-report`, relançable manuellement avec une date en entrée.
