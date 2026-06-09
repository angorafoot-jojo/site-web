# L'Évangile du Royaume — Site web

Site officiel du ministère **L'Évangile du Royaume** — plateforme de ressources bibliques (vidéos, audios, livres numériques, articles, radio, louange).

🌐 **Site en production** : [levangileduroyaume.com](https://levangileduroyaume.com)

---

## Prérequis

- **Node.js 20+** (pour les scripts de validation et génération)
- Un navigateur moderne pour les tests
- Git

Aucun framework, aucun bundler. Le site est du HTML/CSS/JavaScript vanilla hébergé sur GitHub Pages.

---

## Lancer le site en local

```bash
# Cloner le repo
git clone https://github.com/angorafoot-jojo/site-web.git
cd site-web

# Démarrer un serveur local
npx serve .
# Le site est accessible sur http://localhost:3000
```

---

## Scripts disponibles

| Commande | Description |
|----------|-------------|
| `node scripts/validate-data.mjs --quick` | Valide les JSON + fichiers locaux (rapide) |
| `node scripts/validate-data.mjs` | Validation complète avec requêtes réseau |
| `node scripts/validate-links.mjs` | Vérifie les liens internes HTML |
| `node scripts/generate-pages.mjs` | Génère les pages individuelles (livres, audios, etc.) |
| `node scripts/generate-rss.mjs` | Génère le flux RSS podcasts |

---

## Workflow de développement

```
dev ──(push)──→ CI Validation
  └──(PR)──→ Validation + merge──→ Deploy GitHub Pages
```

Tout le développement se fait sur la branche **`dev`**. Le déploiement en production n'a lieu que via une PR vers `main` après validation CI.

👉 Voir [`.github/WORKFLOW.md`](.github/WORKFLOW.md) pour les détails complets.

---

## Structure du projet

```
/
├── *.html                  → Pages du site
├── assets/
│   ├── css/                → Feuilles de style
│   ├── js/                 → Modules JavaScript
│   ├── data/               → Données JSON (contenu)
│   ├── images/             → Images et icônes
│   ├── books/              → Fichiers EPUB
│   └── audio/              → Fichiers audio locaux (petits)
├── scripts/                → Scripts Node.js (validation, génération)
├── .github/
│   ├── workflows/          → CI/CD GitHub Actions
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── WORKFLOW.md
├── ARCHITECTURE.md         → Structure technique détaillée
├── CONTENT_GUIDE.md        → Ajouter/modifier du contenu
└── DEPLOYMENT.md           → Déploiement en production
```

---

## Documentation

| Document | Pour qui | Contenu |
|----------|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Développeurs | Structure des fichiers, conventions, modules JS |
| [CONTENT_GUIDE.md](CONTENT_GUIDE.md) | Contributeurs | Ajouter livres, audios, vidéos, articles |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Mainteneurs | Déployer, vérifier, rollback |
| [CLAUDE.md](CLAUDE.md) | Claude AI | Constitution du projet (règles architecture) |
| [.github/WORKFLOW.md](.github/WORKFLOW.md) | Développeurs | Workflow git, CI, branches |

---

## Stack technique

| Composant | Solution |
|-----------|----------|
| HTML/CSS/JS | Vanilla — aucun framework |
| Hébergement | GitHub Pages |
| Domaine | levangileduroyaume.com |
| Radio | AzuraCast (auto-hébergé) |
| Lecteur EPUB | epub.js 0.3.93 + JSZip 3.10.1 via jsDelivr |
| Audio | Backblaze B2 |
| Vidéo | YouTube (youtube-nocookie.com) |
| CI/CD | GitHub Actions |
