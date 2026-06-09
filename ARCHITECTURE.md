# Architecture technique — L'Évangile du Royaume

Ce document décrit la structure technique du projet, les conventions de code et le cycle de vie d'une modification.

---

## Principe général

Site **statique** HTML/CSS/JS vanilla. Aucun framework, aucun serveur backend.

- Les **données** vivent dans `assets/data/*.json`
- Les **pages** sont des fichiers `.html` à la racine
- Le **rendu dynamique** est assuré par JavaScript côté client
- Le **déploiement** est automatique via GitHub Actions → GitHub Pages

---

## Structure des dossiers

```
/
├── assets/
│   ├── css/
│   │   ├── style.css           → Variables globales, reset, typographie
│   │   ├── layout.css          → Grilles et containers
│   │   ├── navigation.css      → Header, menu mobile, dropdown
│   │   ├── forms.css           → Formulaire de contact
│   │   ├── reader.css          → Lecteur EPUB (modale)
│   │   ├── media-player.css    → Player audio sticky
│   │   └── pages/              → Styles spécifiques par page
│   ├── js/
│   │   ├── main.js             → Navigation, menu mobile, comportements globaux
│   │   ├── nav.js              → Injection du header/footer (composant partagé)
│   │   ├── utils.js            → escapeHtml(), formatDuration(), fonctions communes
│   │   ├── search.js           → Module de recherche/filtrage côté client
│   │   ├── epub-reader.js      → Lecteur EPUB (epub.js + JSZip, lazy-load)
│   │   ├── media-player.js     → Player audio sticky (audios + podcasts)
│   │   ├── modal-player.js     → Modale vidéo YouTube / Drive
│   │   ├── video-renderer.js   → Rendu des sections vidéo depuis videos.json
│   │   ├── book-catalogue.js   → Catalogue livres depuis books.json
│   │   ├── radio-player.js     → Lecteur radio AzuraCast
│   │   ├── error-monitor.js    → Surveillance des erreurs JS (console)
│   │   └── pages/              → Scripts d'initialisation par page
│   │       ├── livres-init.js
│   │       ├── articles-init.js
│   │       ├── audios-init.js
│   │       ├── podcasts-init.js
│   │       ├── louange-init.js
│   │       ├── partners-init.js
│   │       ├── radio-schedule-init.js
│   │       └── index-init.js
│   ├── data/
│   │   ├── books.json          → Livres numériques
│   │   ├── articles.json       → Articles / études
│   │   ├── audios.json         → Messages audio
│   │   ├── podcasts.json       → Épisodes de podcast
│   │   ├── videos.json         → Vidéos YouTube
│   │   ├── louange.json        → Cantiques de louange
│   │   ├── partners.json       → Partenaires / liens
│   │   └── radio-schedule.json → Grille horaire radio
│   ├── images/                 → Images, favicon, og-images
│   └── books/                  → Fichiers EPUB (assets/books/*.epub)
├── scripts/
│   ├── validate-data.mjs       → Validation JSON + médias
│   ├── validate-links.mjs      → Validation liens internes HTML
│   ├── generate-pages.mjs      → Génération pages individuelles
│   └── generate-rss.mjs        → Génération flux RSS podcasts
└── .github/
    └── workflows/
        ├── ci.yml              → Validation + déploiement
        ├── radio-healthcheck.yml
        └── radio-rotation.yml
```

---

## Namespace JavaScript

Tous les modules partagés s'attachent à `window.EduRoyaume` :

```js
window.EduRoyaume = {
  escapeHtml,        // utils.js
  formatDuration,    // utils.js
  Search: { init },  // search.js
  // ...
}
```

Chaque module vérifie la présence de ses dépendances avant de s'activer.

---

## Conventions JSON

### Champs obligatoires (tous les types)

| Champ | Type | Description |
|-------|------|-------------|
| `id` | string | Identifiant unique dans le fichier |
| `title` | string | Titre affiché |
| `slug` | string | Identifiant URL (minuscules, tirets) |
| `type` | string | Type de contenu (`book`, `audio`, `video`…) |
| `source` | string | Origine (`local`, `backblaze`, `youtube`, `drive`) |

### Champs spécifiques par type

**books.json / articles.json**
```json
{
  "id": "livre-001",
  "title": "Titre du livre",
  "slug": "titre-du-livre",
  "author": "Auteur",
  "year": 2023,
  "type": "book",
  "source": "local",
  "epub": "assets/books/titre-du-livre.epub",
  "pdf": "https://...",
  "series": "Série",
  "tags": ["tag1", "tag2"],
  "summary": "Résumé court (optionnel)"
}
```

**audios.json / podcasts.json**
```json
{
  "id": "audio-001",
  "title": "Titre du message",
  "slug": "titre-du-message",
  "date": "2024-01-15",
  "type": "audio",
  "source": "backblaze",
  "url": "https://f005.backblazeb2.com/...",
  "series": "Série",
  "duration": "45:30"
}
```

**videos.json**
```json
{
  "id": "video-001",
  "title": "Titre de la vidéo",
  "slug": "titre-de-la-video",
  "date": "2024-01-15",
  "type": "video",
  "source": "youtube",
  "youtube_id": "dQw4w9WgXcQ",
  "series": "Série",
  "meta": "Mots-clés supplémentaires pour la recherche"
}
```

---

## Sécurité — règles absolues

1. **`escapeHtml()`** sur toute valeur insérée via `innerHTML`
2. **`rel="noopener noreferrer"`** sur tous les `target="_blank"`
3. **Pas de secrets** dans le code (clés API, tokens)
4. **Validation JSON** avant rendu (champs requis, IDs uniques)

```js
// Exemple correct
container.innerHTML = '<h2>' + EduRoyaume.escapeHtml(item.title) + '</h2>';

// Incorrect — XSS possible
container.innerHTML = '<h2>' + item.title + '</h2>';
```

---

## Cycle de vie d'une modification

```
1. git checkout dev
2. Modifier le JSON ou le code
3. node scripts/validate-data.mjs --quick   (vérification locale)
4. npx serve . → tester dans le navigateur
5. git add + git commit
6. git push → CI s'exécute sur dev (GitHub Actions)
7. PR dev → main → CI valide → merge → déploiement automatique
```

---

## Génération des pages individuelles

`scripts/generate-pages.mjs` lit chaque JSON et génère des pages HTML statiques dans des dossiers dédiés :

```
livres/[slug]/index.html
audios/[slug]/index.html
articles/[slug]/index.html
videos/[slug]/index.html
podcasts/[slug]/index.html
```

Ces pages incluent les métadonnées SEO (title, description, canonical, schema.org) et un lien vers le lecteur correspondant.

Ce script s'exécute automatiquement lors du déploiement CI (jamais besoin de committer les pages générées).

---

## Lecteur EPUB

EPUB.js et JSZip sont **lazy-loadés** : ils ne sont téléchargés que lorsque l'utilisateur clique "Lire" pour la première fois.

- Position de lecture sauvegardée : `localStorage['epub_pos_v1_[id]']`
- Préférences (mode, taille) : `localStorage['epub_pref_mode']`, `localStorage['epub_pref_font']`
- Auto-récupération : si une position sauvegardée cause une erreur EPUB, le lecteur efface la clé et réouvre le livre depuis le début.

---

## Limitations connues

### Lecteur EPUB — Compatibilité navigateurs (T66)

| Navigateur | Statut | Notes |
|------------|--------|-------|
| Chrome desktop | ✅ Fonctionnel | Référence de développement |
| Firefox desktop | ✅ Fonctionnel | Mineurs différences de rendu de polices |
| Safari macOS | ✅ Fonctionnel | Testé sur macOS 14+ |
| Safari iOS | ⚠️ Partiel | epub.js utilise un `<iframe>` sandboxé ; sur iOS 15 et inférieur certains EPUB avec polices embarquées peuvent ne pas se charger. La navigation par pages fonctionne ; le mode défilement peut sembler saccadé sur anciens appareils. |
| Chrome Android | ✅ Fonctionnel | |

**Mitigation sur Safari iOS** :
- epub.js 0.3.93 est la version la plus stable disponible sur CDN jsDelivr.
- L'auto-recovery (T47) efface la position sauvegardée si l'ouverture échoue, évitant les boucles d'erreur.
- Le lien PDF de secours (`btn-reader-dl`) reste toujours accessible en cas d'échec EPUB.

### Autres limitations

- **Google Drive** : utilisé pour quelques audios anciens (instable, à migrer vers Backblaze B2).
- **Header/footer** : injectés via `nav.js` (composant JS) — dépendance à ce fichier sur toutes les pages.
- **Miniatures YouTube** : `img.youtube.com/vi/[id]/mqdefault.jpg` peut retourner une image noire pour les vidéos privées/supprimées plutôt qu'une erreur 404. Un `onerror` dans `video-renderer.js` affiche un placeholder SVG dans ce cas.
