# L'Évangile du Royaume — Site web

Site officiel du ministère **L'Évangile du Royaume** — plateforme de ressources bibliques (vidéos, audios, livres numériques, articles, radio, louange).

🌐 **Site déployé (GitHub Pages)** : [angorafoot-jojo.github.io/site-web](https://angorafoot-jojo.github.io/site-web/)  
🎯 **Domaine cible** : [levangileduroyaume.com](https://levangileduroyaume.com) — ⚠️ sert encore l'ancien site WordPress, bascule DNS à faire (voir ci-dessous)  
📦 **Repo GitHub** : [angorafoot-jojo/site-web](https://github.com/angorafoot-jojo/site-web)

---

## État du projet (à jour : juillet 2026)

Le nouveau site est **fonctionnel, complet et déployé sur GitHub Pages**. La migration issue de l'audit technique (couche données JSON, CDN, composants partagés, CI/CD, SEO) est terminée, et l'audit de prod-readiness du 03/07 est vert sur tout **sauf la bascule du domaine**.

### Ce qui fonctionne
- Navigation (header/footer injectés par `nav.js`)
- Lecteur audio sticky (prev/next, volume, reprise de position)
- Lecteur EPUB (pages/défilement, zoom, sauvegarde de position)
- Recherche + filtres côté client (livres, articles, audios, vidéos)
- Cantiques YouTube (modale vidéo)
- Player radio AzuraCast en direct — voir [`Radio/README.md`](Radio/README.md)
- Page **Nouveau** data-driven (dernières parutions + lecture directe)
- Toutes les données en JSON (`assets/data/`) — plus aucune donnée hardcodée
- Toutes les images en local (`assets/images/`) — plus aucune dépendance Unsplash
- CDN audio/PDF sur **Backblaze B2** (plus de Google Drive)
- Protection XSS (`escapeHtml`), Sentry, SRI sur CDN
- Accessibilité **WCAG AA** sur les contrastes (lot corrigé juin 2026)
- SEO (title, meta, OpenGraph, schema.org)
- Responsive mobile
- CI/CD GitHub Actions (validation + déploiement automatique)

### Ce qui reste

| Priorité | Sujet | Action |
|----------|-------|--------|
| 🔴 **Bloquant prod** | **Le domaine sert encore l'ancien WordPress** (DNS apex → 216.172.184.159 ; GitHub Pages API : `cname: null`) | Saisir le domaine dans *Settings → Pages* du repo (le fichier `CNAME` ne suffit pas en build "workflow"), **puis** basculer le DNS : A → 185.199.108/109/110/111.153, `www` → CNAME `angorafoot-jojo.github.io`. ⚠️ Ne pas toucher au sous-domaine `parole-prophetique-fm.levangileduroyaume.com` (radio AzuraCast, fonctionne) |
| 🟡 Important | **Erreurs console Sentry** à confirmer sur le site live | Vérifier dans un vrai navigateur que le monitoring d'erreurs remonte bien |
| 🟢 Planifié | **Mesure de performance** réelle | Lancer Lighthouse sur le site live (le serveur local fausse les scores) ; envisager minification/fingerprinting des assets |
| 🟢 Planifié | **Tests a11y automatisés** | Intégrer axe-core / pa11y au pipeline CI |
| 🟢 Planifié | **`style.css` monolithique** (~1600 lignes) | Découper par responsabilité (§5 de CLAUDE.md) ; dédupliquer le composant `.type-tabs` copié dans 3 CSS de page |

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

> ℹ️ `npx serve` sert des **URLs propres** : utiliser `http://localhost:3000/audios` (et non `/audios.html`).

### ⚠️ Cache-busting après toute modification CSS/JS

Les feuilles de style sont liées avec un numéro de version, p. ex. `style.css?v=contrast-aa-2`.
**À chaque fois que tu modifies un fichier `.css` (ou `.js`), incrémente ce numéro** dans les `<link>`/`<script>` des pages HTML concernées.

Sans ça, GitHub Pages (cache ~10 min) sert l'ancien fichier aux visiteurs après le déploiement, et le navigateur garde la version en cache. La version est unifiée sur toutes les pages (`?v=contrast-aa-N`) — passer à `contrast-aa-3`, etc.

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
├── Radio/                  → Système radio AzuraCast (scripts Python, plans, rapports)
├── .github/
│   ├── workflows/          → CI/CD site (ci.yml) + 8 workflows radio (radio-*.yml)
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── WORKFLOW.md
├── _headers                → Headers HTTP (préparation Cloudflare Pages/Netlify — PAS lu par GitHub Pages, la CSP est injectée par nav.js)
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
| [Radio/README.md](Radio/README.md) | Mainteneur radio | Système radio AzuraCast : blocs, scripts, workflows, API |
| [.github/WORKFLOW.md](.github/WORKFLOW.md) | Développeurs | Workflow git, CI, branches |
| [CLAUDE.md](CLAUDE.md) | Claude AI | Constitution du projet (règles architecture) |

---

## Stack technique

| Composant | Solution |
|-----------|----------|
| HTML/CSS/JS | Vanilla — aucun framework |
| Hébergement | GitHub Pages |
| Domaine | levangileduroyaume.com (cible — bascule DNS depuis WordPress à faire) |
| Radio | AzuraCast (Parole Prophétique FM) — voir [Radio/README.md](Radio/README.md) |
| Lecteur EPUB | epub.js 0.3.93 + JSZip 3.10.1 via jsDelivr (SRI) |
| Audio / PDF CDN | Backblaze B2 |
| Vidéo | YouTube embed (youtube-nocookie.com) |
| Contact | Email direct (nousecrire@levangileduroyaume.com) — plus de formulaire |
| Monitoring | Sentry (browser SDK) |
| CI/CD | GitHub Actions |
