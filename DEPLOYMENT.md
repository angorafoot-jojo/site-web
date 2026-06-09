# Guide de déploiement

Ce document décrit les étapes pour mettre le site en production, configurer le DNS, vérifier un déploiement et effectuer un rollback.

---

## 1. Configuration DNS (à faire une seule fois)

Le fichier `CNAME` est déjà présent dans le repo (`levangileduroyaume.com`). Il faut maintenant configurer le DNS chez le registrar du domaine.

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

## 4. Corriger le formulaire de contact (Formspree)

Le formulaire de contact utilise Formspree mais l'ID est invalide.

**Étapes :**
1. Créer un compte sur [formspree.io](https://formspree.io)
2. Créer un nouveau formulaire → copier l'ID (format `xyzabcde`)
3. Ouvrir `assets/js/contact-form.js`
4. Remplacer `YOUR_FORM_ID` par le vrai ID

```javascript
// assets/js/contact-form.js — ligne à modifier
fetch('https://formspree.io/f/YOUR_FORM_ID',  // ← remplacer YOUR_FORM_ID
```

5. Tester depuis un navigateur en navigation privée (soumettre le formulaire)
6. Vérifier la réception dans le tableau de bord Formspree

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
- [ ] DNS configuré et HTTPS actif
- [ ] Formulaire de contact testé (navigation privée)
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
| URL AzuraCast | `assets/js/pages/radio-schedule-init.js` |
| ID Formspree | `assets/js/contact-form.js` |
| Contenu (livres, articles…) | `assets/data/*.json` |
