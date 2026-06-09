# Guide de contribution au contenu

Ce guide explique comment ajouter ou modifier du contenu sur le site sans toucher au code.

> **Règle d'or** : le contenu vit dans `assets/data/*.json`. On ne modifie jamais le HTML pour ajouter un livre, une vidéo ou un audio.

---

## Sommaire

- [Ajouter un livre](#ajouter-un-livre)
- [Ajouter un audio / message](#ajouter-un-audio--message)
- [Ajouter un podcast](#ajouter-un-podcast)
- [Ajouter une vidéo YouTube](#ajouter-une-vidéo-youtube)
- [Ajouter un article](#ajouter-un-article)
- [Ajouter un cantique de louange](#ajouter-un-cantique-de-louange)
- [Modifier un partenaire](#modifier-un-partenaire)
- [Valider les données](#valider-les-données)

---

## Ajouter un livre

**Fichier** : `assets/data/books.json`

1. Ajouter le fichier EPUB dans `assets/books/` (format `titre-slug.epub`)
2. Ajouter une entrée dans `books.json` :

```json
{
  "id": "livre-[numéro]",
  "title": "Titre du livre",
  "slug": "titre-du-livre",
  "author": "Prénom Nom",
  "year": 2024,
  "type": "book",
  "source": "local",
  "epub": "assets/books/titre-du-livre.epub",
  "pdf": "",
  "series": "Nom de la série (ou vide)",
  "tags": ["tag1", "tag2"],
  "summary": "Une ou deux phrases de présentation (optionnel)"
}
```

**Champs obligatoires** : `id`, `title`, `slug`, `type`, `source`

**Vérifier** :
- L'`id` est unique dans le fichier
- Le `slug` ne contient que des lettres minuscules, chiffres et tirets
- Le fichier EPUB est bien présent dans `assets/books/`

---

## Ajouter un audio / message

**Fichier** : `assets/data/audios.json`

L'audio doit être hébergé sur **Backblaze B2** (ne pas utiliser Google Drive comme source principale).

```json
{
  "id": "audio-[numéro]",
  "title": "Titre du message",
  "slug": "titre-du-message",
  "date": "2024-06-15",
  "type": "audio",
  "source": "backblaze",
  "url": "https://f005.backblazeb2.com/file/audio-site-web/nom-du-fichier.mp3",
  "series": "Nom de la série",
  "speaker": "Nom du prédicateur",
  "duration": "45:30",
  "summary": "Résumé court (optionnel)"
}
```

**Format de la date** : `YYYY-MM-DD`

**Uploader sur Backblaze B2** :
1. Se connecter sur [backblaze.com](https://www.backblaze.com)
2. Aller dans le bucket `audio-site-web`
3. Uploader le fichier MP3
4. Copier l'URL publique dans le champ `url`

---

## Ajouter un podcast

**Fichier** : `assets/data/podcasts.json`

Même format que les audios. Le flux RSS est généré automatiquement depuis ce fichier lors du déploiement.

```json
{
  "id": "podcast-[numéro]",
  "title": "Titre de l'épisode",
  "slug": "titre-de-lepisode",
  "date": "2024-06-15",
  "type": "podcast",
  "source": "backblaze",
  "url": "https://f005.backblazeb2.com/file/audio-site-web/nom-fichier.mp3",
  "series": "Nom du podcast",
  "duration": "32:10",
  "description": "Description de l'épisode pour le flux RSS"
}
```

---

## Ajouter une vidéo YouTube

**Fichier** : `assets/data/videos.json`

Récupérer l'ID YouTube depuis l'URL de la vidéo :
`https://www.youtube.com/watch?v=`**`dQw4w9WgXcQ`** → l'ID est `dQw4w9WgXcQ`

```json
{
  "id": "video-[numéro]",
  "title": "Titre de la vidéo",
  "slug": "titre-de-la-video",
  "date": "2024-06-15",
  "type": "video",
  "source": "youtube",
  "youtube_id": "dQw4w9WgXcQ",
  "series": "Nom de la série",
  "meta": "Mots-clés supplémentaires pour la recherche interne",
  "summary": "Résumé court (optionnel)"
}
```

Les vidéos sont regroupées par `series` sur la page Vidéos.

---

## Ajouter un article

**Fichier** : `assets/data/articles.json`

Un article peut avoir un EPUB, un PDF, ou les deux.

```json
{
  "id": "article-[numéro]",
  "title": "Titre de l'article",
  "slug": "titre-de-larticle",
  "author": "Prénom Nom",
  "date": "2024-06-15",
  "type": "article",
  "source": "local",
  "epub": "assets/books/titre-de-larticle.epub",
  "pdf": "",
  "series": "Série ou catégorie",
  "tags": ["tag1"],
  "summary": "Résumé court"
}
```

---

## Ajouter un cantique de louange

**Fichier** : `assets/data/louange.json`

```json
{
  "id": "cantique-[numéro]",
  "title": "Titre du cantique",
  "slug": "titre-du-cantique",
  "type": "louange",
  "source": "youtube",
  "youtube_id": "ID_YOUTUBE",
  "duration": "4:25",
  "album": "Nom de l'album",
  "artist": "Artiste"
}
```

---

## Modifier un partenaire

**Fichier** : `assets/data/partners.json`

```json
{
  "id": "partner-[numéro]",
  "name": "Nom de l'organisation",
  "url": "https://...",
  "logo": "assets/images/partners/nom-logo.png",
  "description": "Courte description",
  "category": "Ministère"
}
```

Le logo doit être placé dans `assets/images/partners/` (format PNG ou SVG, max 100 KB).

---

## Valider les données

Avant de pousser une modification, vérifier que les JSON sont valides :

```bash
node scripts/validate-data.mjs --quick
```

Cette commande vérifie :
- ✅ Syntaxe JSON correcte
- ✅ Champs obligatoires présents
- ✅ IDs uniques dans chaque fichier
- ✅ Fichiers EPUB locaux présents

En cas d'erreur, le message indique le fichier et la ligne concernés.

---

## Règles importantes

- **Ne jamais dépasser 100 MB** pour un fichier EPUB
- **Toujours utiliser des slugs uniques** (minuscules, tirets, pas d'accents)
- **Le champ `id` est permanent** — ne pas le modifier après publication (utilisé par les URL des pages individuelles)
- **Les données Google Drive** sont temporaires — tout nouvel audio doit aller sur Backblaze B2
