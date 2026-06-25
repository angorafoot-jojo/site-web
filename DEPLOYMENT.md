# Guide de déploiement

Ce document décrit les étapes pour mettre le site en production, configurer le DNS, vérifier un déploiement et effectuer un rollback.

---

## 1. Configuration DNS (déjà fait — référence)

> ✅ Le domaine custom `levangileduroyaume.com` est **déjà configuré et en HTTPS**. Cette section sert de référence en cas de migration de registrar ou de réinstallation.

Le fichier `CNAME` est présent dans le repo (`levangileduroyaume.com`). Les enregistrements DNS chez le registrar :

### Enregistrements à ajouter

| Type | Nom | Valeur | Description |
|------|-----|--------|-------------|
| `A` | `@` | `185.199.108.153` | GitHub Pages IP |
| `A` | `@` | `185.199.109.153` | GitHub Pages IP |
| `A` | `@` | `185.199.110.153` | GitHub Pages IP |
| `A` | `@` | `185.199.111.153` | GitHub Pages IP |
| `CNAME` | `www` | `angorafoot-jojo.github.io` | Alias www |

### Vérifier que ça fonctionne

```bash
# Vérifier que le DNS se propage (attendre 5-30 min après modification)
dig levangileduroyaume.com A +short
# Doit retourner une des 4 IPs de GitHub Pages

curl -sI https://levangileduroyaume.com | grep HTTP
# Doit retourner HTTP/2 200
```

### Activer HTTPS dans GitHub Settings

```
GitHub → Settings → Pages → Custom domain → levangileduroyaume.com
☑ Enforce HTTPS  (cocher après que le certificat SSL soit émis — ~10 min)
```

> ⚠️ Si l'ancien site est encore sur `levangileduroyaume.com`, la migration DNS va le remplacer immédiatement. S'assurer que le nouveau site est prêt avant de changer le DNS.

---

## 2. Prérequis GitHub Settings (à vérifier une seule fois)

### Activer GitHub Pages via Actions

```
GitHub → Settings → Pages
→ Source : "GitHub Actions"
```

### Protéger la branche `main` (recommandé)

```
GitHub → Settings → Branches → Add rule → "main"
  ☑ Require a pull request before merging
  ☑ Require status checks to pass before merging
    → Sélectionner le job "validate"
```

---

## 3. Déploiement normal (via PR)

Le déploiement est **automatique** après chaque merge vers `main`. Aucune commande manuelle.

```
1. Travailler sur la branche dev
2. Ouvrir une PR : dev → main sur GitHub
3. Attendre que le CI passe (job "Validation JSON + liens")
4. Merger la PR
5. Le job "Déploiement" se déclenche automatiquement
6. Le site est en ligne en ~2 minutes sur levangileduroyaume.com
```

Suivre la progression dans **GitHub → onglet Actions**.

---

## 4. ⚠️ Cache-busting après modification CSS / JS

Les feuilles de style et scripts sont liés avec un numéro de version dans les pages HTML, p. ex. :

```html
<link rel="stylesheet" href="assets/css/style.css?v=contrast-aa-2">
<link rel="stylesheet" href="assets/css/pages/audios.css?v=contrast-aa-2">
```

**Règle obligatoire : à chaque modification d'un fichier `.css` ou `.js`, incrémenter ce numéro de version** (`contrast-aa-2` → `contrast-aa-3`, etc.) sur **toutes les pages** qui référencent le fichier modifié.

Pourquoi : GitHub Pages sert les assets avec un cache (~10 min) et le navigateur du visiteur garde l'ancienne version. Sans changement d'URL (`?v=`), une partie des visiteurs voit l'ancien CSS/JS après le déploiement.

Astuce pour tout aligner d'un coup (depuis la racine du repo) :

```bash
# Remplace l'ancienne version par la nouvelle dans toutes les pages HTML
grep -rl '?v=contrast-aa-2' *.html | xargs sed -i '' 's/?v=contrast-aa-2/?v=contrast-aa-3/g'
```

> Le `<base href="/">` des sous-pages (livres/, audios/…) n'est PAS concerné — seuls les `?v=` des `<link>`/`<script>` le sont.

---

## 5. Checklist avant un déploiement critique

### Contenu
- [ ] JSON valides : `node scripts/validate-data.mjs --quick`
- [ ] Liens internes : `node scripts/validate-links.mjs`
- [ ] Fichiers EPUB présents dans `assets/books/` et `assets/articles/`
- [ ] Liens audio Backblaze testés en navigation privée

### Pages
- [ ] Chaque page modifiée a un `<title>` et un `<meta description>` uniques
- [ ] `sitemap.xml` contient les nouvelles pages (si applicable)
- [ ] Console navigateur sans erreur sur les pages modifiées

### Responsive
- [ ] Testé mobile (< 480 px) via DevTools
- [ ] Testé desktop (Chrome + Firefox)
- [ ] Lecteur audio testé sur iOS Safari (si modifié)

### Production
- [ ] HTTPS actif (domaine custom déjà configuré)
- [ ] Numéros de version `?v=` incrémentés si CSS/JS modifié (voir section 4)
- [ ] Radio joue correctement
- [ ] Un EPUB s'ouvre dans le lecteur

---

## 6. Vérifier un déploiement

Après mise en ligne, tester dans cet ordre :

1. **Accueil** : [levangileduroyaume.com](https://levangileduroyaume.com) — articles, vidéo YouTube
2. **Livres** : ouvrir un EPUB, vérifier la position sauvegardée
3. **Audios** : lancer une piste, vérifier prev/next
4. **Cantiques** : cliquer sur une vignette YouTube → vidéo joue dans la modale
5. **Radio** : bouton "Écouter en direct" → flux joue
6. **Console navigateur** : F12 → aucune erreur rouge

---

## 7. Rollback

### Option 1 — Reverter la PR (recommandé)

```
GitHub → Pull Requests → Closed → [la PR problématique]
→ "Revert" → Merger la PR de revert
```

Le CI redéploie automatiquement la version précédente.

### Option 2 — Revert Git manuel

```bash
git checkout dev
git revert [hash-du-commit-problématique]
git push
# Ouvrir une PR dev → main
```

### Option 3 — Redéploiement sans modification

```
GitHub → Actions → "CI — Validation & Déploiement"
→ "Run workflow" → Sélectionner "main" → "Run workflow"
```

---

## 8. Note sur le déploiement en sous-dossier (staging)

Le site est conçu pour tourner à la **racine d'un domaine** (`levangileduroyaume.com/`).

Les pages dans `livres/`, `articles/`, `audios/`, `podcasts/`, `videos/` utilisent `<base href="/">` pour que les chemins relatifs résolvent depuis la racine.

**Conséquence :** sur l'URL de staging `angorafoot-jojo.github.io/site-web/`, les sous-pages sont cassées (les assets résolvent vers `angorafoot-jojo.github.io/assets/...` au lieu de `.../site-web/assets/...`).

**Ce n'est pas un bug** — c'est le comportement attendu. Pour tester les sous-pages, utiliser le serveur local (`npx serve .` → `localhost:3000`) ou la production avec le domaine custom configuré.

---

## 9. Variables de configuration

Le site ne contient aucune variable d'environnement secrète. Toutes les URLs sont publiques.

| Ce qui peut changer | Où modifier |
|---------------------|-------------|
| URL audio Backblaze | `assets/data/audios.json` et `assets/data/podcasts.json` |
| URL stream radio | `assets/data/radio-schedule.json` et `assets/js/nav.js` |
| Système radio (blocs, scripts, API) | voir [`Radio/README.md`](Radio/README.md) |
| Version cache des assets (`?v=`) | `<link>`/`<script>` dans les `*.html` (voir section 4) |
| Contenu (livres, articles…) | `assets/data/*.json` |
