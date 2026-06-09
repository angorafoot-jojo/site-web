# L'Évangile du Royaume — Site web

Site officiel du ministère **L'Évangile du Royaume** — plateforme de ressources bibliques (vidéos, audios, livres numériques, articles, radio, louange).

🌐 **Site en production** : [levangileduroyaume.com](https://levangileduroyaume.com)  
📦 **Repo GitHub** : [angorafoot-jojo/site-web](https://github.com/angorafoot-jojo/site-web)

---

## État du projet (juin 2026)

Le site est **fonctionnel et déployé**. Toutes les fonctionnalités principales marchent.

### Ce qui fonctionne
- Navigation (header/footer injectés par `nav.js`)
- Lecteur audio sticky (prev/next, volume, reprise de position)
- Lecteur EPUB (pages/défilement, zoom, sauvegarde de position)
- Recherche + filtres côté client (livres, articles, audios, vidéos)
- Cantiques YouTube et Google Drive (modale vidéo)
- Player radio AzuraCast en direct
- Toutes les données en JSON (`assets/data/`)
- Protection XSS, CSP, Sentry, SRI sur CDN
- SEO (title, meta, OpenGraph, schema.org)
- Responsive mobile
- CI/CD GitHub Actions (validation + déploiement automatique)

### Ce qui reste à faire

| Priorité | Problème | Fichier | Action |
|----------|----------|---------|--------|
| 🔴 Critique | **Formspree ID invalide** — le formulaire ne fonctionne pas | `assets/js/contact-form.js` | Remplacer `YOUR_FORM_ID` par le vrai ID Formspree du compte |
| 🟡 Important | **Certains fichiers EPUB manquants** — livres sans fichier local | `assets/books/`, `assets/data/books.json` | Ajouter les `.epub` manquants ou retirer les entrées JSON |
| 🟡 Important | **Quelques audios sur Google Drive** — instable | `assets/data/audios.json` | Migrer vers Backblaze B2 |
| 🟢 Planifié | **DNS à configurer** — voir section Déploiement | DNS registrar | Pointer `levangileduroyaume.com` vers GitHub Pages |

---

## Prérequis

- **Node.js 20+** (pour les scripts de validation et génération)
- Un navigateur moderne pour les tests
- Git

Aucun framework, aucun bundler, aucune dépendance à installer. Le site est du HTML/CSS/JavaScript vanilla hébergé sur GitHub Pages.

---

## Lancer le site en local

```bash
# Cloner le repo
git clone https://github.com/angorafoot-jojo/site-web.git
cd site-web

# Démarrer un serveur local (port 3000)
npx serve .
```

Le site est accessible sur **http://localhost:3000**

> ⚠️ Ne pas ouvrir les fichiers `.html` directement dans le navigateur (file://). Les `fetch()` vers les JSON échoueront. Toujours passer par `npx serve .`.

---

## Scripts disponibles

| Commande | Description |
|----------|-------------|
| `node scripts/validate-data.mjs --quick` | Valide les JSON + fichiers locaux (rapide) |
| `node scripts/validate-data.mjs` | Validation complète avec requêtes réseau |
| `node scripts/validate-links.mjs` | Vérifie tous les liens internes HTML |
| `node scripts/generate-pages.mjs` | Génère les pages individuelles (livres, audios, etc.) |
| `node scripts/generate-rss.mjs` | Génère le flux RSS podcasts |

---

## Workflow de développement

```
dev ──(push)──→ CI Validation (JSON + liens)
  └──(PR → main)──→ Validation + merge──→ Deploy GitHub Pages automatique
```

- Tout le développement se fait sur la branche **`dev`**
- Le déploiement en production n'a lieu que via une PR vers `main` validée par le CI
- Un push direct sur `main` déclenche aussi le déploiement (pour les corrections urgentes)

👉 Voir [`.github/WORKFLOW.md`](.github/WORKFLOW.md) pour les détails complets.

---

## Structure du projet

```
/
├── *.html                  → Pages du site (racine)
├── livres/                 → Pages individuelles des livres (générées)
├── articles/               → Pages individuelles des articles (générées)
├── audios/                 → Pages individuelles des audios (générées)
├── podcasts/               → Pages individuelles des podcasts (générées)
├── videos/                 → Pages individuelles des vidéos (générées)
├── assets/
│   ├── css/                → Feuilles de style (1 fichier par responsabilité)
│   ├── js/                 → Modules JavaScript (1 fichier par responsabilité)
│   ├── data/               → Données JSON — tout le contenu est ici
│   ├── images/             → Images et icônes
│   ├── books/              → Fichiers EPUB des livres
│   └── articles/           → Fichiers EPUB des articles
├── scripts/                → Scripts Node.js (validation, génération)
├── .github/
│   ├── workflows/          → CI/CD GitHub Actions
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── WORKFLOW.md
├── CNAME                   → Domaine custom levangileduroyaume.com
├── sitemap.xml             → Plan du site pour les moteurs de recherche
├── robots.txt              → Directives pour les robots
├── README.md               → Ce fichier
├── ARCHITECTURE.md         → Structure technique détaillée
├── CONTENT_GUIDE.md        → Ajouter/modifier du contenu
├── DEPLOYMENT.md           → Déploiement et configuration DNS
└── CLAUDE.md               → Règles d'architecture (pour Claude AI)
```

---

## Documentation

| Document | Pour qui | Contenu |
|----------|----------|---------|
| **[DEPLOYMENT.md](DEPLOYMENT.md)** | Dev / Mainteneur | **Lire en premier** — DNS, mise en ligne, vérification |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Développeurs | Structure des fichiers, conventions, modules JS |
| [CONTENT_GUIDE.md](CONTENT_GUIDE.md) | Contributeurs | Ajouter livres, audios, vidéos, articles |
| [.github/WORKFLOW.md](.github/WORKFLOW.md) | Développeurs | Workflow git, CI, branches |
| [CLAUDE.md](CLAUDE.md) | Claude AI | Constitution du projet (règles architecture) |

---

## Stack technique

| Composant | Solution |
|-----------|----------|
| HTML/CSS/JS | Vanilla — aucun framework |
| Hébergement | GitHub Pages |
| Domaine | levangileduroyaume.com |
| DNS | À configurer — voir DEPLOYMENT.md |
| Radio | AzuraCast (Parole Prophétique FM) |
| Lecteur EPUB | epub.js 0.3.93 + JSZip 3.10.1 via jsDelivr (SRI) |
| Audio CDN | Backblaze B2 |
| Vidéo | YouTube embed (youtube-nocookie.com) |
| Formulaire | Formspree (ID à corriger — voir section "Ce qui reste") |
| Monitoring | Sentry (browser SDK) |
| CI/CD | GitHub Actions |
