# Radio — Parole Prophétique FM

Documentation du système de radio automatisée **Parole Prophétique FM** de L'Évangile du Royaume.

- **Station** : `evangile_du_royaume` — diffusion 24h/24, 7j/7
- **Plateforme** : [AzuraCast](https://www.azuracast.com/) (Liquidsoap + Icecast)
- **Écoute** : `https://parole-prophetique-fm.levangileduroyaume.com`
- **Fuseau station** : **UTC** (tous les horaires ci-dessous sont en UTC)

> ⚠️ Objectif spirituel : préserver l'ordre **jingle → message du jour → Bible → louange** et ne jamais interrompre le message du jour. Toute modification doit respecter cet ordre.

---

## 1. Architecture — 4 blocs de 6 h

La journée est découpée en 4 blocs. Chaque bloc rejoue **le même message du jour** mais avec une Bible / musique / jingles différents.

| Playlist | Plage horaire (UTC) | ID API |
|----------|---------------------|--------|
| `BLOC_A_SERIE_DU_JOUR` | 00h02 – 05h59 | 30 |
| `BLOC_B_SERIE_DU_JOUR` | 06h00 – 11h59 | 31 |
| `BLOC_C_SERIE_DU_JOUR` | 12h00 – 17h59 | 32 |
| `BLOC_D_SERIE_DU_JOUR` | 18h00 – 23h59 | 33 |
| `000_TRANSITION` | minuit (jingle de bascule) | — |

**Structure d'un bloc** : `jingle → message du jour → jingle → Bible ~60min → jingle → musique ~60min → jingle → Bible ~30min → …`

### Playlists sources (bibliothèques — ne PAS activer en diffusion directe)

| Playlist | ID API | Contenu |
|----------|--------|---------|
| `001_LA_MUSIQUE` | 22 | Louange / cantiques |
| `002_BIBLE AUDIO` | 23 | Bible audio |
| `014_Jingles` | 29 | Jingles |
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

Tous les horaires sont en **UTC**. La rotation et le reset sont déclenchés **de l'extérieur par [cron-job.org](https://cron-job.org)** via `workflow_dispatch`, car le cron natif de GitHub Actions était retardé de 2 à 5 h (file d'attente partagée) — ce qui faisait démarrer le BLOC_A bien après minuit.

| Workflow | Horaire (UTC) | Déclencheur | Rôle |
|----------|---------------|-------------|------|
| `radio-rotation.yml` | ~23h30 | cron-job.org → `workflow_dispatch` | Avance la rotation : choisit le message du jour suivant et remplit les 4 blocs |
| `radio-midnight-reset.yml` | 00h00 | cron-job.org → `workflow_dispatch` | Redémarre l'AutoDJ et vide la file pour que les blocs repartent de la position 1 (jingle → message) |
| `radio-healthcheck.yml` | toutes les 15 min | cron GitHub | Vérifie que le flux diffuse |
| `radio-playback-report.yml` | 01h00 | cron GitHub | Génère le rapport de diffusion de la veille |
| `radio-validate-paths.yml` | 12h00 | cron GitHub | Vérifie que chaque chemin de la config existe dans la médiathèque |
| `radio-test-playlists.yml` | manuel | `workflow_dispatch` | Test : vérifie les playlists via l'API |
| `radio-test-restart.yml` | manuel | `workflow_dispatch` | Test : restart AutoDJ + vérification du pointeur |

---

## 3. Scripts Python

Tous dans `Radio/`. Dépendance unique : `requests` (`pip install -r requirements.txt`).

| Script | Rôle |
|--------|------|
| `azuracast_rotation_4_blocs.py` | **Script principal de rotation** — sélectionne le message du jour et remplit les 4 blocs. Budget par bloc : message + bible + louange ≈ créneau (dépassement ≤ ~2 min). Les fichiers < 7 s (jingle tronqué, fragment) sont écartés de la rotation |
| `azuracast_rotation_cycle_builder.py` | Construit le cycle de rotation des séries |
| `restart_autodj.py` | Redémarre l'AutoDJ et vide la file (reset de minuit) |
| `playback_report.py` | Génère le rapport de diffusion quotidien |
| `validate_paths.py` | Vérifie que chaque chemin de la config existe dans la médiathèque |
| `retitle_bible_files.py` | Réécrit les métadonnées (titre + artiste) des fichiers bibliques |
| `set_jingle_fades.py` | Désactive le crossfade sur les jingles |
| `test_azuracast_rotation.py` | Tests unitaires de la logique de rotation |

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

## 4. API AzuraCast

- **Station ID** : `1`
- **Auth** : header `Authorization: Bearer <CLÉ_API>`
- **La clé API vit UNIQUEMENT dans les GitHub Secrets** — jamais dans le code ni dans un fichier committé.

```bash
BASE="https://parole-prophetique-fm.levangileduroyaume.com/api/station/1"

# Lister les playlists
curl -H "Authorization: Bearer $CLE" "$BASE/playlists"

# Fichiers d'une playlist (ex. musique = 22)
curl -H "Authorization: Bearer $CLE" "$BASE/files?playlist=22&limit=2"
```

Champs utiles renvoyés : `id`, `path`, `title`, `length` (secondes), `length_text`, `playlists`.

---

## 5. Configuration & secrets

| Élément | Emplacement |
|---------|-------------|
| Clé API AzuraCast | **GitHub Secrets** (jamais committée) |
| Config de rotation (exemple) | `azuracast_rotation_config.example.json` *(suivi)* |
| Config de rotation (réelle, avec clé) | `azuracast_rotation_config.json` *(gitignoré)* |
| État de la rotation | `azuracast_rotation_state.json` *(suivi, persistant)* |
| Musique source locale | `Radio/ParoleProphetiqueFM-musique/` — **2,5 Go, gitignoré, ne jamais committer** (uploader dans AzuraCast) |

> Pièges connus : les accents macOS (NFD) vs AzuraCast (NFC) à l'upload des fichiers ; `track_sensitive=false` dans Liquidsoap peut couper un message au changement de bloc (d'où le reset de minuit + le créneau BLOC_A à 00h02).

---

## 6. En cas de problème

1. **Le flux est muet** → vérifier le workflow `radio-healthcheck` (Actions) ; relancer `radio-midnight-reset` manuellement.
2. **Mauvais message diffusé / blocs désynchronisés** → relancer `radio-rotation` puis `radio-midnight-reset`.
3. **Un fichier ne joue pas** → lancer `validate_paths.py` (ou le workflow `radio-validate-paths`) pour repérer un chemin manquant.
4. **Rapport de diffusion** → workflow `radio-playback-report` (sortie : commit `chore: rapport diffusion radio`).
