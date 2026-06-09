# Guide de déploiement

Ce document décrit les étapes pour déployer le site en production, vérifier un déploiement et effectuer un rollback si nécessaire.

---

## Déploiement normal (via PR)

Le déploiement est **automatique** après un merge vers `main`. Il n'y a pas de commande manuelle à lancer.

```
1. Ouvrir une PR : dev → main sur GitHub
2. Attendre que le CI passe (job "Validation")
3. Merger la PR
4. Le job "Déploiement" se déclenche automatiquement
5. Le site est en ligne en ~2 minutes
```

Voir la progression dans **GitHub → onglet Actions**.

---

## Prérequis GitHub Settings (à faire une seule fois)

Ces réglages activent le déploiement via GitHub Actions et bloquent les pushs directs vers `main`.

### 1. Activer GitHub Pages via Actions

```
GitHub → Settings → Pages
→ Source : "GitHub Actions"
```

Sans ce réglage, GitHub Pages déploie la branche `main` directement, sans passer par le CI.

### 2. Protéger la branche `main` (recommandé)

```
GitHub → Settings → Branches → Add rule → "main"
  ☑ Require a pull request before merging
  ☑ Require status checks to pass before merging
    → Sélectionner le job "validate"
  ☑ Require branches to be up to date before merging
```

---

## Checklist avant un déploiement critique

Avant de merger une PR importante :

### Contenu
- [ ] Tous les fichiers JSON sont valides : `node scripts/validate-data.mjs --quick`
- [ ] Tous les liens internes sont corrects : `node scripts/validate-links.mjs`
- [ ] Les fichiers EPUB référencés existent dans `assets/books/`
- [ ] Les liens Backblaze répondent (tester un lien audio en navigation privée)

### Pages
- [ ] Chaque page modifiée a un `<title>` et un `<meta description>` uniques
- [ ] `sitemap.xml` contient les nouvelles pages (si applicable)
- [ ] Aucune erreur JS dans la console navigateur

### Responsive
- [ ] Testé sur mobile (< 480 px) via les outils développeur
- [ ] Testé sur desktop (Chrome ou Firefox)
- [ ] Lecteur audio fonctionnel sur iOS Safari (si modifié)

---

## Vérifier un déploiement

Après le déploiement, vérifier les points critiques :

1. **Page d'accueil** : [levangileduroyaume.com](https://levangileduroyaume.com)
2. **Vidéos** : la recherche filtre correctement
3. **Livres** : ouvrir un EPUB, vérifier la position sauvegardée
4. **Radio** : le player affiche "En direct" et joue le flux
5. **Console navigateur** : aucune erreur

---

## Rollback

Si un déploiement casse le site :

### Option 1 — Reverter la PR (recommandé)

```
GitHub → Pull Requests → Closed → [la PR problématique]
→ "Revert" → Merger la PR de revert
```

Le CI redéploie automatiquement la version précédente.

### Option 2 — Rollback Git manuel

```bash
# Trouver le commit de la bonne version
git log --oneline -10

# Créer une PR de revert depuis dev
git checkout dev
git revert [hash-du-commit-problématique]
git push
# Ouvrir une PR dev → main
```

### Option 3 — Force push sur main (dernier recours)

```bash
# ATTENTION : destructif, ne fait que si Options 1 et 2 échouent
git checkout main
git reset --hard [hash-du-bon-commit]
git push --force-with-lease
```

---

## Déploiement manuel (workflow_dispatch)

Pour redéployer sans modifier le code :

```
GitHub → Actions → "CI — Validation & Déploiement"
→ "Run workflow" → Sélectionner "main" → "Run workflow"
```

---

## Variables de configuration

Le site ne contient aucune variable d'environnement secrète. Tous les URLs sont publics.

Si une URL de service change (Backblaze, AzuraCast…) :
- Mettre à jour directement dans les fichiers JSON (`assets/data/`)
- Mettre à jour les références dans le code si nécessaire
- Passer par le workflow normal (PR dev → main)

---

## Régénération des pages individuelles

Les pages individuelles (ex : `livres/[slug]/index.html`) sont générées **automatiquement** à chaque déploiement par `scripts/generate-pages.mjs`.

Il ne faut **pas** committer ces fichiers générés dans le repo.

Pour les tester en local :

```bash
node scripts/generate-pages.mjs
npx serve .
# Tester http://localhost:3000/livres/[slug]/
```
