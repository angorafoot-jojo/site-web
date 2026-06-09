## Description

<!-- Résumez ce qui a changé et pourquoi. -->

## Type de modification

- [ ] Correction de bug
- [ ] Nouvelle fonctionnalité
- [ ] Refactorisation / nettoyage
- [ ] Données (JSON, médias)
- [ ] Documentation

## Fichiers modifiés

<!-- Listez les fichiers impactés. -->

---

## Checklist avant merge

### Qualité du code
- [ ] Aucun `style=`, `onclick=`, `<script>` inline dans le HTML
- [ ] Toute insertion `innerHTML` utilise `escapeHtml()`
- [ ] Tous les liens `target="_blank"` ont `rel="noopener noreferrer"`
- [ ] Aucune donnée dupliquée (collections dans JSON, pas dans le HTML)

### Fonctionnalité
- [ ] Testé sur desktop (Chrome ou Firefox)
- [ ] Testé sur mobile (ou responsive dev tools < 480 px)
- [ ] Navigation clavier fonctionnelle sur les éléments modifiés
- [ ] Console navigateur sans erreur JS

### JSON (si modifié)
- [ ] JSON syntaxiquement valide (`node scripts/validate-data.mjs --quick`)
- [ ] Champs obligatoires présents (`id`, `title`, `slug`, `type`, `source`)
- [ ] IDs uniques dans le fichier

### SEO (si nouvelle page ou page modifiée)
- [ ] `<title>` unique
- [ ] `<meta name="description">` unique
- [ ] `<link rel="canonical">` présent
- [ ] `sitemap.xml` mis à jour si nouvelle page

### Performance (si nouveau composant)
- [ ] Ressources lourdes lazy-loadées (EPUB.js, iframes YouTube)
- [ ] Aucune image > 200 KB non compressée

---

## Tests à effectuer par le reviewer

<!-- Décrivez les étapes manuelles à suivre pour vérifier la PR. -->

1.
2.
3.
