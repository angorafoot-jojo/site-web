# CLAUDE.md — Constitution du projet

# L'Évangile du Royaume

Ce document définit les règles absolues que Claude doit suivre.

Le but n'est PAS uniquement de produire du code fonctionnel.

Le but est de construire un système :

- fiable
- maintenable
- performant
- sécurisé
- évolutif
- simple à comprendre
- simple à modifier
- simple à tester

Une solution rapide qui crée de la dette technique n'est PAS une bonne solution.

**Contexte :** site religieux / plateforme média statique. Maintenu par Jonathan + des contributeurs non-développeurs.

---

## 1. Philosophie du projet

Avant de coder, toujours privilégier dans cet ordre :

1. Simplicité
2. Réutilisation
3. Scalabilité
4. Lisibilité
5. Performance
6. Accessibilité
7. Sécurité
8. SEO technique
9. Maintenance
10. Robustesse

Le code doit pouvoir être compris par un développeur découvrant le projet dans 2 ans.

---

## 2. Processus obligatoire AVANT d'écrire du code

Avant toute modification, Claude doit répondre aux questions suivantes.

### Nature de la tâche

Est-ce :

- bug local ?
- amélioration ?
- nouvelle fonctionnalité ?
- refactorisation ?
- changement d'architecture ?

### Impact

- Quels fichiers seront touchés ?
- Quels composants seront impactés ?
- Est-ce que plusieurs pages sont concernées ?

### Réutilisation

- Cette logique existe-t-elle déjà ?
- Puis-je la partager ?
- Puis-je créer un composant commun ?
- Puis-je éviter la duplication ?

### Scalabilité

Cette solution fonctionne-t-elle avec 10 éléments ? 100 ? 1000 ?

- Le temps de chargement augmente-t-il ?
- La maintenance augmente-t-elle ?

### Dette technique

Cette modification crée-t-elle : duplication, dépendance, complexité, dette, risque futur ?

Si oui, Claude doit le signaler **avant** de coder.

### Librairies

Avant de réinventer une fonctionnalité, comparer solution maison vs librairie open source.

Critères : maintenance, poids, licence, activité, accessibilité, compatibilité GitHub Pages, simplicité.

Une librairie n'est utilisée que si elle réduit réellement la complexité.

---

## 3. Règles d'architecture

### Données

Les données vivent dans `assets/data/`. Jamais dans le HTML. Jamais dans du JavaScript hardcodé.

Fichiers attendus :

```
assets/data/
  books.json
  articles.json
  audios.json
  videos.json
  podcasts.json
  louange.json
  partners.json
  schedule.json
```

Chaque objet possède au minimum : `id`, `title`, `slug`, `date` ou `year`, `type`, `source`.

### Architecture cible

Le projet doit converger progressivement vers :

```
assets/
  css/
  js/
  data/
  images/
  books/
  audio/
components/
  header/
  footer/
  media-player/
  epub-reader/
  cards/
layouts/
scripts/
  validate-data
  validate-links
  build-sitemap
  build-search
.github/
  workflows/
```

Aucune nouvelle fonctionnalité ne doit éloigner le projet de cette architecture.

---

## 4. HTML

Le HTML contient uniquement : structure, accessibilité, placeholders.

Jamais : données répétitives, contenu de collections, logique complexe.

Interdit :

```
onclick=
onchange=
onkeydown=
onkeyup=
style=
<script> inline
<style> inline
```

---

## 5. CSS

Jamais de style inline. Un fichier par responsabilité.

```
assets/css/
  style.css        → variables globales, reset, typographie
  layout.css       → grilles, containers
  navigation.css   → header, menu mobile, dropdown
  forms.css        → formulaire contact
  reader.css       → lecteur EPUB
  media-player.css → player audio sticky
  pages/           → styles spécifiques par page si nécessaire
```

---

## 6. JavaScript

Un fichier par responsabilité. Pas de duplication.

```
assets/js/
  main.js          → navigation, menu mobile, comportements globaux
  media-player.js  → lecteur audio partagé (audios + podcasts)
  epub-reader.js   → lecteur EPUB partagé (livres + articles)
  data-loader.js   → chargement et rendu des fichiers JSON
  search.js        → recherche et filtres côté client
  utils.js         → escapeHtml, formatDuration, fonctions communes
```

---

## 7. Médias

- Audio local > 10 MB : interdit. Héberger sur CDN (Cloudflare R2, Backblaze B2).
- EPUB.js et JSZip : lazy-load uniquement au clic "Lire".
- YouTube iframe : chargé uniquement au clic.
- Google Drive : uniquement si aucune alternative. Jamais comme source principale.
- Images OG : fichier local `assets/images/og-[page].jpg`, jamais Unsplash.

---

## 8. Accessibilité

Une tâche n'est pas terminée si :

- navigation clavier cassée
- focus invisible
- Escape absent sur une modale
- modale sans focus trap
- `div` cliquable à la place d'un `button` ou `a`
- `alt` absent sur une image
- `aria-label` absent sur un bouton icône
- contraste insuffisant (ratio < 4.5:1 pour le texte)

---

## 9. Sécurité

Obligatoire sur chaque modification :

- `escapeHtml()` sur toute valeur insérée via `innerHTML`
- `rel="noopener noreferrer"` sur tous les liens `target="_blank"`
- Validation des données JSON avant rendu
- Pas de secrets dans le code (clés API, tokens)
- SRI (`integrity` + `crossorigin`) recommandé pour les CDN

---

## 10. SEO

Chaque page possède :

- `<title>` unique
- `<meta name="description">` unique
- `<link rel="canonical">`
- un seul `<h1>`
- balises OpenGraph
- balises Twitter Card
- `schema.org` si pertinent (Book, AudioObject, RadioStation, Article…)

`sitemap.xml` et `robots.txt` à jour après chaque nouvelle page.

---

## 11. Performance

Avant chaque ajout demander :

- Est-ce lazy-loadé ?
- Est-ce compressé ?
- Est-ce cacheable ?
- Est-ce vraiment nécessaire ?
- Est-ce que cela dégrade Lighthouse ?

Les iframes et lecteurs lourds sont toujours différés.

---

## 12. Anti-duplication

Copier plus de 20 lignes est interdit.

Avant de copier, Claude doit proposer : composant, template, JSON, fonction commune, module ou script partagé.

---

## 13. Validation obligatoire avant de terminer une tâche

- JSON valide (pas d'erreur de syntaxe)
- Liens internes fonctionnels
- Fichiers référencés (EPUB, PDF, MP3) présents
- Rendu correct mobile (< 480px) et desktop
- Navigation clavier fonctionnelle sur les éléments modifiés
- Console navigateur propre (pas d'erreur JS)

---

## 14. Dette technique

Toute dette doit être déclarée avec :

- Cause
- Impact
- Raison pour laquelle elle est acceptée temporairement
- Plan de suppression

Aucune dette cachée.

---

## 15. Ordre de migration

Le projet évolue progressivement dans cet ordre. Pas de réécriture totale sans plan.

1. Stabiliser (corriger les bugs bloquants)
2. Extraire les données (JSON pour tous les contenus)
3. Mutualiser les composants (header, footer, players)
4. Ajouter validation automatique (scripts + CI)
5. Optimiser SEO (schema.org, pages individuelles)
6. Optimiser performance (lazy-load, Lighthouse)
7. Nettoyer la duplication (CSS, JS)

---

## 16. Rapport obligatoire après chaque tâche

Claude termine toujours par :

- **Fichiers modifiés** : liste
- **Pourquoi** : raison des changements
- **Dette restante** : ce qui n'a pas été traité et pourquoi
- **Risques** : ce qui pourrait casser
- **Tests à effectuer** : actions manuelles à valider
- **Prochaine amélioration recommandée** : une seule, concrète

---

## 17. Principe fondamental

Claude n'est pas un générateur de code.

Claude est l'architecte logiciel du projet.

Son objectif est de laisser le projet dans un meilleur état qu'avant chaque modification.

Aucune modification ne doit augmenter la complexité globale sans justification explicite.

---

## 18. État actuel du projet (juin 2026)

### Dette technique connue — à traiter dans l'ordre

| Priorité | Problème | Fichier(s) | Action |
|----------|----------|------------|--------|
| 🔴 Critique | Formspree URL invalide | `contact.html` | Remplacer par un vrai ID Formspree |
| 🔴 Critique | Header/footer dupliqués dans 13 pages | Tous les `.html` | Centraliser via composant JS |
| 🔴 Critique | Données livres hardcodées | `livres.html` | Migrer vers `assets/data/books.json` |
| 🔴 Critique | Données audios hardcodées | `audios.html` | Migrer vers `assets/data/audios.json` |
| 🟡 Important | EPUB.js chargé au démarrage | `livres.html`, `articles.html` | Lazy-load au clic |
| 🟡 Important | Lecteur audio dupliqué | `audios.html`, `podcasts.html` | Mutualiser dans `media-player.js` |
| 🟡 Important | Google Drive utilisé pour l'audio | `audios.html`, `podcasts.html` | Migrer vers CDN |
| 🟡 Important | SVG sprite inline répété | Tous les `.html` | Externaliser dans `assets/images/icons.svg` |
| 🟢 Planifié | Pas de CI/CD | `.github/workflows/` | Ajouter GitHub Actions minimal |
| 🟢 Planifié | Pas de schema.org | Toutes les pages | Ajouter JSON-LD par type de contenu |

### Ce qui fonctionne bien — ne pas casser

- Lecteur EPUB : mode pages/défilement, zoom, sauvegarde position localStorage
- Player audio sticky : prev/next, volume, barre de progression
- Recherche + filtres côté client sur les livres
- Protection XSS via `escapeHtml()` sur toutes les insertions innerHTML
- Responsive mobile sur toutes les pages
- Navigation avec dropdown desktop et menu hamburger mobile
- `sitemap.xml` et `robots.txt` en place et pointant vers `levangileduroyaume.com`

### Checklist avant mise en production

- [ ] Formspree : tester l'envoi réel depuis un navigateur incognito
- [ ] Tous les fichiers EPUB référencés existent dans `assets/books/`
- [ ] Tous les liens PDF répondent (HEAD request)
- [ ] Tous les liens Google Drive testés en navigation privée
- [ ] Header correct sur mobile (< 480px) et desktop
- [ ] Lecteur audio fonctionne sur iOS Safari
- [ ] Lecteur EPUB fonctionne sur Chrome et Safari
- [ ] `sitemap.xml` contient toutes les pages actives
- [ ] Console navigateur sans erreur sur toutes les pages

---

## 19. Stack technique

| Composant | Solution |
|-----------|----------|
| HTML/CSS/JS | Vanilla, pas de framework |
| Hébergement | GitHub Pages |
| Domaine | levangileduroyaume.com |
| Radio | AzuraCast (Parole Prophétique FM) |
| Formulaire | Formspree (ID à corriger) |
| Lecteur EPUB | epub.js 0.3.93 + JSZip 3.10.1 (CDN) |
| Audio externe | Google Drive (temporaire → CDN) |
| Vidéo | YouTube embed |
| CDN audio cible | Cloudflare R2 ou Backblaze B2 |
