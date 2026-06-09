# Workflow de déploiement — L'Évangile du Royaume

## Vue d'ensemble

```
dev  ──── (push) ──→  CI Validation  ──→  (résultat visible dans Actions)
  |
  └── (PR vers main) ──→  CI Validation  ──→  merge si OK  ──→  Deploy GitHub Pages
```

Le site public (`levangileduroyaume.com`) n'est mis à jour **que** si :
1. La PR est ouverte depuis `dev` vers `main`
2. Le CI passe (validation JSON + liens internes)
3. Le merge est effectué manuellement

---

## Branches

| Branche | Rôle | Déclenchement CI | Déploiement |
|---------|------|-----------------|-------------|
| `main`  | Production — site public | Oui (push + PR) | Oui → GitHub Pages |
| `dev`   | Développement en cours | Oui (push) | Non |

**Règle :** tout développement se fait sur `dev` (ou une branche feature). On ne pousse jamais directement sur `main`.

---

## Workflow quotidien

### 1. Travailler sur `dev`

```bash
git checkout dev
git pull origin dev
# ... modifications ...
git add <fichiers>
git commit -m "feat: description courte"
git push
```

Le CI se déclenche automatiquement et signale les erreurs dans l'onglet **Actions** de GitHub.

### 2. Ouvrir une PR vers `main`

Sur GitHub → **Pull Requests** → **New pull request**

- Base : `main`
- Compare : `dev`
- Remplir le PR template (checklist)

Le CI re-valide la PR. Si tout est vert → merge autorisé.

### 3. Merge et déploiement

Après le merge, le CI redéploie automatiquement le site sur GitHub Pages.
Le déploiement prend environ 1–2 minutes.

---

## Protections de branche (configuration manuelle requise)

Ces règles doivent être activées manuellement dans **GitHub → Settings → Branches → Branch protection rules** pour la branche `main` :

- [ ] **Require a pull request before merging** — interdit les pushs directs
- [ ] **Require status checks to pass before merging** — sélectionner le job `validate`
- [ ] **Require branches to be up to date before merging**

> ⚠️ Sans ces règles, un push direct vers `main` déploie immédiatement sans validation.

---

## URL de prévisualisation (optionnel)

GitHub Pages ne génère pas d'URL de prévisualisation par PR. Pour obtenir une vraie URL de staging :

**Option A — Cloudflare Pages (gratuit)**
1. Connecter le repo sur [pages.cloudflare.com](https://pages.cloudflare.com)
2. Configurer la branche `dev` comme branche de déploiement secondaire
3. Cloudflare génère une URL automatique par branche (ex : `dev.levangileduroyaume.pages.dev`)

**Option B — GitHub Pages sur un repo séparé**
1. Fork ou second repo `site-web-staging`
2. Déployer `dev` sur ce repo (workflow séparé)

Pour l'instant, la validation CI + les tests manuels en local suffisent.

---

## Commandes utiles

```bash
# Vérifier la validation localement (comme en CI)
node scripts/validate-data.mjs --quick
node scripts/validate-links.mjs

# Serveur local de prévisualisation
npx serve .

# Voir l'état de la CI
# → GitHub → onglet Actions
```
