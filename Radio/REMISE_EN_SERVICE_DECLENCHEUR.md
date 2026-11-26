# Remise en service du déclencheur externe (cron-job.org)

**À quoi sert cette fiche** : tenir à jour les **5 jobs** cron-job.org qui déclenchent la
rotation, le reset de minuit et la garde de frontière. Les 2 premiers sont rétablis depuis
le 24/11/2026 ; les 3 de la garde restent à créer. Le récit de la panne et les réglages de
référence servent aussi de mode d'emploi pour la prochaine fois.

**État au 26/11/2026** — ✅ **rotation et reset rétablis**, il reste la garde de frontière.

- **Les 2 jobs historiques n'ont jamais voulu se réactiver.** Ils ont été remplacés par des
  **jobs neufs** le 24/11 ; les anciens restent désactivés (leur historique date la panne).
- **Deux nuits vérifiées** : rotation à 23:30:54 puis 23:31:03 UTC, reset à 00:01:10 puis
  00:01:13 — toutes en `workflow_dispatch` et en succès. Rapport du 25/11 : ponctualité ✅,
  0 coupure, 0 double message, file saine.
- **Les 3 jobs de la garde de frontière existent aussi** depuis le 25/11 : départs vérifiés
  à 06:01:1x, 12:01:1x et 18:01:1x UTC en `workflow_dispatch`. Les 5 jobs sont donc en place.
- **Reste à faire** : **fermer l'issue #18**, et mesurer dans quelques jours si la garde
  retire enfin des doublons maintenant qu'elle arrive à l'heure.
- **Leçon à garder** : un job que cron-job.org a désactivé peut refuser de repartir. Ne pas
  s'acharner — en recréer un neuf prend 5 minutes et c'est ce qui a débloqué la situation.

Contexte et cause de la panne : `AUDIT_2026-11-17.md` §5 · fiche de la dépendance :
`README.md` §6.

---

## Avant de commencer

| | |
|---|---|
| **Où** | <https://console.cron-job.org/> — compte Google personnel de Jonathan (cf. `README.md` §6) |
| **Token** | Le PAT fine-grained créé le 19/11/2026 (`Actions: Read and write`, dépôt `site-web` seul, sans expiration). Il vit **dans cron-job.org uniquement**. S'il est perdu : en recréer un sur <https://github.com/settings/personal-access-tokens/new> |
| **Durée** | ~20 min : 10 pour réparer les 2 jobs désactivés, 10 pour créer les 3 de la garde (le 1er en prend 5, les 2 autres se dupliquent) |
| **Risque** | Nul à l'antenne : un dispatch de rotation hors heure est un no-op (idempotence), et la garde de frontière ne fait que lire la file |

### Test du token, avant toute chose (optionnel, 10 s)

Déclenche la garde de frontière, qui n'a **aucun effet** sur l'antenne. Réponse attendue : `204`.

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" -H "Authorization: Bearer COLLER_LE_TOKEN_ICI" https://api.github.com/repos/angorafoot-jojo/site-web/actions/workflows/radio-boundary-guard.yml/dispatches -d '{"ref":"main"}'
```

`204` = le token est bon. `401` = token mort ou mal copié. `404` = le token n'a pas accès
au dépôt (ou le nom de workflow est faux).

---

## Étape 1 — réparer les 2 jobs existants (10 min)

**Les modifier, ne pas les supprimer** : leur historique d'exécutions est la seule trace
datée de la panne, et il servira à prouver que la remise en service a bien pris.

Pour **« Rotation Radio AzuraCast (libre) »** puis **« Transitions »** :

1. **Ouvrir l'historique d'abord** et noter le code HTTP de l'échec du 10/11. `401` =
   token expiré, ce qui confirme le diagnostic de l'audit. Un autre code (`404`, `422`)
   voudrait dire que la cause est ailleurs et change la suite — me le dire.
2. **Vérifier l'URL en entier** (la liste la tronque) : elle doit finir par
   `/actions/workflows/radio-rotation.yml/dispatches` pour la rotation et
   `/actions/workflows/radio-midnight-reset.yml/dispatches` pour « Transitions ».
   ⚠️ Les noms de ces jobs ne disent pas quel workflow ils appellent — ne pas se fier au titre.
3. **Remplacer l'en-tête `Authorization`** par `Bearer <le token du 19/11>`. L'ancien est
   mort : c'est lui qui a fait tomber les jobs.
4. **Vérifier l'heure et le fuseau** : 23h30 **UTC** pour la rotation, 00h00 **UTC** pour
   le reset. Le fuseau est le piège n°1 (voir la table des pièges en bas).
5. **Réactiver le job** (`Inactif` → actif) et enregistrer.
6. Pendant qu'on y est : activer la **notification en cas d'échec** et
   l'**enregistrement des réponses**. Sans la première, la prochaine panne sera encore
   silencieuse ; sans la seconde, on ne saura pas pourquoi.

Renommer au passage en « Radio — rotation 23h30 UTC » et « Radio — reset minuit 00h00 UTC »
évite la prochaine confusion : « Transitions » ne dit pas qu'il s'agit du reset de minuit.

---

### Si un job refuse de se réactiver (constaté le 24/11/2026)

Les 2 jobs historiques n'ont pas voulu repasser en actif. **Ne pas s'acharner : le but est
que la radio reparte à l'heure, pas que ces deux jobs-là survivent.**

1. **Vérifier qu'on active au bon endroit** : dans la liste, la colonne `Inactif` est un
   état, pas forcément un interrupteur. Il faut **ouvrir le job**, cocher
   *Enable job* / *Activer* dans le formulaire, puis **enregistrer**. Un champ refusé
   (URL, planification, en-tête) empêche l'enregistrement — le message est affiché en haut
   du formulaire, pas à côté du bouton.
2. **Test décisif, sans risque** : créer **un job neuf** sur
   `radio-boundary-guard.yml` (aucun effet à l'antenne), planifié dans 5 minutes.
   - Il part → le problème est **sur ces 2 vieux jobs** : les laisser désactivés et passer
     au plan B.
   - Il ne part pas non plus → le problème est **sur le compte** (limite, vérification
     e-mail, compte en sommeil). Regarder les e-mails de cron-job.org et le bandeau du
     tableau de bord ; aucune modification de job n'y changera rien.
3. **Plan B — recréer les 5 jobs à neuf** (c'est l'étape 2 ci-dessous, appliquée aux 5).
   Les 2 anciens restent désactivés : ils ne gênent pas, et leur historique garde la trace
   datée de la panne. Un job créé avant 23h30 UTC rattrape **la nuit même**.
4. **Plan C — si le compte lui-même est bloqué** : le déclencheur doit changer de maison.
   L'alternative déjà chiffrée dans l'audit est un cron sur le VPS AzuraCast, qui doit de
   toute façon tourner 24/7 (`AUDIT_2026-11-17.md` §5 étape 4). Trois pannes de ce tiers en
   cinq mois, plus celle-ci : la question n'est plus théorique.

---

## Étape 2 — créer les jobs neufs

**Ordre de priorité** : d'abord les 2 qui tiennent l'antenne — rotation 23h30 UTC et reset
00h00 UTC. Les 3 jobs de la garde de frontière (06h01/12h01/18h01) n'ont jamais existé et
peuvent attendre le lendemain : sans eux, un doublon de message passe parfois à une
frontière de bloc, alors que sans les deux premiers c'est toute la nuit qui dérape.

⚠️ **Ne pas utiliser « Run now » pour tester ces deux jobs-là.** La rotation reconstruit
les playlists, dont celle en cours de diffusion ; le reset redémarre Liquidsoap et coupe le
titre à l'antenne. Pour vérifier qu'un job part, utiliser un job sur
`radio-boundary-guard.yml` : il ne fait que lire la file. Les deux autres se vérifient
**après coup**, à leur heure, avec les commandes de la section « Vérification ».

---

## Les 5 jobs — réglages de référence

Réglages **identiques pour les cinq**, seuls le titre, l'heure et l'URL changent :

| Réglage | Valeur |
|---------|--------|
| Méthode | `POST` |
| Corps de la requête | `{"ref":"main"}` |
| En-tête 1 | `Accept` → `application/vnd.github+json` |
| En-tête 2 | `Authorization` → `Bearer <le token>` |
| En-tête 3 | `X-GitHub-Api-Version` → `2022-11-28` |
| En-tête 4 | `Content-Type` → `application/json` |
| Fuseau horaire du job | **UTC** ⚠️ le piège n°1 : par défaut cron-job.org prend le fuseau du compte |
| Exécution | tous les jours, à la minute indiquée |
| Réponse attendue | `204 No Content` |

### Job 1 — Rotation quotidienne · **23:30 UTC**

```
https://api.github.com/repos/angorafoot-jojo/site-web/actions/workflows/radio-rotation.yml/dispatches
```

### Job 2 — Reset AutoDJ à minuit · **00:00 UTC**

```
https://api.github.com/repos/angorafoot-jojo/site-web/actions/workflows/radio-midnight-reset.yml/dispatches
```

### Jobs 3, 4 et 5 — Garde de frontière · **06:01**, **12:01** et **18:01 UTC**

Même URL pour les trois, seule l'heure change :

```
https://api.github.com/repos/angorafoot-jojo/site-web/actions/workflows/radio-boundary-guard.yml/dispatches
```

> Ces trois-là n'ont **jamais** existé. C'est pour ça que la garde est verte depuis le
> 26/08 sans avoir retiré un seul doublon : son cron GitHub arrive 1 à 5 h après la
> frontière, quand le doublon est déjà passé à l'antenne.

---

## Pas à pas dans l'interface — création des 3 jobs de la garde

*(libellés constatés le 21/11/2026 — l'interface peut évoluer ; les valeurs ci-dessus, elles, ne changent pas. Pour les 2 jobs existants, voir l'étape 1 : on les modifie, on ne les recrée pas.)*

1. **Create cronjob**.
2. **Title** : `Radio — rotation 23h30 UTC` (puis `reset`, `garde 06h01`, etc.).
3. **URL** : coller l'URL du job.
4. **Schedule** : *Every day*, heure et minute du tableau — **et régler le sélecteur de
   fuseau sur UTC**, pas sur l'heure de Montréal.
5. Ouvrir **Advanced** :
   - **Request method** → `POST`
   - **Headers** → les 4 lignes du tableau
   - **Request body** → `{"ref":"main"}`
6. **Notifications** : activer l'alerte en cas d'échec — c'est le seul endroit où un `401`
   se verra avant le lendemain matin.
7. **Save responses in job history** : activer. Sans ça, l'historique ne montre pas le code
   HTTP, et on ne peut plus diagnostiquer après coup.
8. **Create** / **Save**.

Pour les 4 suivants : dupliquer le premier job et ne changer que le titre, l'heure et
l'URL — ça évite de recoller le token quatre fois.

---

## Vérification, le lendemain matin

```bash
gh run list --workflow radio-rotation.yml --limit 3 --json createdAt,event -q '.[]|[.createdAt,.event]|@tsv'
```

```bash
gh run list --workflow radio-midnight-reset.yml --limit 3 --json createdAt,event -q '.[]|[.createdAt,.event]|@tsv'
```

**Attendu** : `workflow_dispatch`, à 23h3x et 00h0x UTC. Si la colonne dit encore
`schedule`, le job n'est pas parti — regarder l'historique du job dans cron-job.org
(code HTTP) avant toute autre hypothèse.

Puis, vers 08h UTC, la ligne **PONCTUALITÉ** en tête de
`Radio/logs/diffusion_<hier>.log` doit être **verte** :

```bash
git pull --quiet && sed -n '4,6p' "Radio/logs/diffusion_$(date -u -v-1d +%F).log"
```

---

## Une fois deux nuits confirmées

- [ ] Fermer l'issue [#18](https://github.com/angorafoot-jojo/site-web/issues/18)
      (« Déclencheur externe défaillant »). ⚠️ **Tant qu'elle est ouverte, la prochaine
      panne du déclencheur n'ouvrira pas d'issue** — elle ne fera qu'ajouter un commentaire
      de plus sous celle-ci, au milieu de ceux de l'ancienne panne.
- [ ] Mettre à jour `README.md` §0 et §6 : date de remise en service, et retirer la mention
      « aucun job n'existe » de cette fiche.
- [ ] Décider du chantier structurel (`AUDIT_2026-11-17.md` §5 étape 4) : déplacer le
      déclenchement sur le VPS AzuraCast, qui doit de toute façon tourner 24/7. Trois pannes
      de ce tiers en cinq mois.

---

## Pièges connus

| Symptôme | Cause | Remède |
|----------|-------|--------|
| Le run part, mais à 23h30 **heure de Montréal** (04h30 UTC) | Fuseau du job laissé sur l'heure locale du compte | Repasser le job en UTC |
| `401` dans l'historique du job | Token expiré, révoqué, ou `Bearer ` manquant devant | Recréer le token, recoller l'en-tête complet |
| `404` | Token sans accès au dépôt, ou nom de fichier de workflow erroné | Vérifier `Actions: Read and write` et le nom exact du `.yml` |
| `422` | Corps de requête absent ou `ref` invalide | Le corps doit être exactement `{"ref":"main"}` |
| Tout est vert côté cron-job.org, rien côté GitHub | Job créé mais laissé **désactivé** | Activer le job |
| Le token est réparé, et pourtant plus rien ne part | **Le job a été désactivé automatiquement** après des échecs répétés — constaté le 24/11/2026 sur les 2 jobs historiques, en échec depuis le 10/11 | Rouvrir chaque job et le réactiver à la main : réparer la cause ne rallume pas le job |
| Un job porte un nom qui ne dit pas ce qu'il déclenche (« Transitions ») | Titre historique, URL tronquée dans la liste | Ouvrir le job, lire l'URL en entier, renommer `Radio — <tâche> <heure> UTC` |
