#!/usr/bin/env node
/* ============================================================
   scripts/generate-pages.mjs
   Génère les pages HTML individuelles pour chaque item de
   chaque JSON de contenu.

   Usage :
     node scripts/generate-pages.mjs         → génère tout
     node scripts/generate-pages.mjs --dry   → liste sans écrire

   Sorties :
     livres/[slug].html      — 57 livres
     audios/[slug].html      — 42 messages audio
     articles/[slug].html    — 16 articles
     videos/[slug].html      — 95 vidéos
     podcasts/[slug].html    — 23 podcasts

   Chaque page générée inclut :
     - <base href="/"> pour résoudre les chemins relatifs
     - title + meta description uniques
     - <link rel="canonical"> vers levangileduroyaume.com
     - balises OpenGraph
     - schema.org JSON-LD (type adapté)
     - navigation via nav.js (header + footer identiques au site)
     - contenu simple : titre, métadonnées, bouton d'action
   ============================================================ */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT      = join(__dirname, '..');
const DATA_DIR  = join(ROOT, 'assets', 'data');
const DRY_RUN   = process.argv.includes('--dry');

const BASE_URL = 'https://levangileduroyaume.com';
const SITE_NAME = "L'Évangile du Royaume";

/* ── Lecture des données ─────────────────────────────────────── */
function loadJson(file) {
  const raw  = readFileSync(join(DATA_DIR, file), 'utf8');
  const data = JSON.parse(raw);
  /* Les JSON utilisent des clés numériques "0","1","2"... */
  return Object.values(data);
}

/* ── Échapper le HTML ────────────────────────────────────────── */
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* ── Créer un répertoire si absent ───────────────────────────── */
function ensureDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

/* ── BreadcrumbList schema.org ───────────────────────────────── */
function breadcrumbSchema(collectionName, collectionUrl, itemName, itemUrl) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    'itemListElement': [
      { '@type': 'ListItem', 'position': 1, 'name': SITE_NAME, 'item': BASE_URL + '/' },
      { '@type': 'ListItem', 'position': 2, 'name': collectionName, 'item': collectionUrl },
      { '@type': 'ListItem', 'position': 3, 'name': itemName, 'item': itemUrl },
    ],
  };
}

/* ── Template HTML de base ───────────────────────────────────── */
function buildPage({ slug, dir, title, description, canonical, ogImage, schemaJson, breadcrumbSchemaJson, pageKey, body }) {
  const og = ogImage || `${BASE_URL}/assets/images/og-default.png`;
  const schemas = [schemaJson, breadcrumbSchemaJson].filter(Boolean);
  return `<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <!-- base href résout tous les assets (CSS/JS/images) depuis la racine -->
  <base href="/">
  <title>${esc(title)} | ${SITE_NAME}</title>
  <meta name="description" content="${esc(description)}">
  <link rel="canonical" href="${canonical}">
  <meta property="og:type"        content="website">
  <meta property="og:url"         content="${canonical}">
  <meta property="og:title"       content="${esc(title)} | ${SITE_NAME}">
  <meta property="og:description" content="${esc(description)}">
  <meta property="og:image"       content="${og}">
  <meta name="twitter:card"       content="summary_large_image">
  <link rel="icon" type="image/svg+xml" href="assets/images/favicon.svg">
  <link rel="icon" type="image/png"     href="assets/images/favicon.png" sizes="32x32">
  <link rel="stylesheet" href="assets/css/style.css">
  <link rel="stylesheet" href="assets/css/pages/detail.css">
  <script type="application/ld+json">
  ${schemas.length === 1 ? JSON.stringify(schemas[0], null, 2) : JSON.stringify(schemas, null, 2)}
  </script>
</head>
<body data-page="${pageKey}">
<script src="assets/js/nav.js"></script>

<main id="main-content">
  <div class="detail-page">
    ${body}
  </div>
</main>

</body>
</html>`;
}

/* ── Breadcrumb HTML ─────────────────────────────────────────── */
function breadcrumb(collectionHref, collectionLabel, currentTitle) {
  return `<nav class="detail-breadcrumb" aria-label="Fil d'ariane">
      <a href="${collectionHref}">${esc(collectionLabel)}</a>
      <span class="detail-breadcrumb__sep" aria-hidden="true">›</span>
      <span aria-current="page">${esc(currentTitle)}</span>
    </nav>`;
}

/* ══════════════════════════════════════════════════════════════
   GÉNÉRATEURS PAR TYPE
══════════════════════════════════════════════════════════════ */

/* ── Livres ──────────────────────────────────────────────────── */
function generateBook(item) {
  const slug      = String(item.slug || item.id);
  const title     = item.title || 'Livre';
  const tags      = Array.isArray(item.tags) ? item.tags : [];
  const canonical = `${BASE_URL}/livres/${slug}.html`;

  const tagBadges = tags.map(t =>
    `<span class="detail-tag">${esc(t)}</span>`
  ).join('');

  const actions = [
    item.epub ? `<a class="detail-btn detail-btn--primary" href="livres.html#livre-${esc(item.id)}">
        <svg width="18" height="18" aria-hidden="true"><use href="#icon-livre"/></svg>
        Lire en ligne
      </a>` : '',
    item.pdf  ? `<a class="detail-btn detail-btn--secondary"
        href="${esc(item.pdf)}" target="_blank" rel="noopener noreferrer">
        Télécharger le PDF
      </a>` : '',
  ].filter(Boolean).join('\n      ');

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Book',
    'name': title,
    'url': canonical,
    'inLanguage': 'fr',
    'publisher': { '@type': 'Organization', 'name': SITE_NAME, 'url': BASE_URL },
    ...(item.pdf  ? { 'sameAs': item.pdf }  : {}),
    ...(tags.length ? { 'keywords': tags.join(', ') } : {}),
  };

  const body = `${breadcrumb('livres.html', 'Bibliothèque', title)}
    <div class="detail-header">
      <span class="detail-header__type">Livre</span>
      <h1 class="detail-header__title">${esc(title)}</h1>
      ${tags.length ? `<div class="detail-tags">${tagBadges}</div>` : ''}
    </div>
    <div class="detail-actions">
      ${actions || `<a class="detail-btn detail-btn--secondary" href="livres.html">Retour à la bibliothèque</a>`}
    </div>
    <a class="detail-back" href="livres.html">← Tous les livres</a>`;

  return buildPage({
    slug, dir: 'livres', title, canonical,
    description: `Lire "${title}" — ${tags.join(', ') || 'enseignement biblique'} sur ${SITE_NAME}.`,
    pageKey: 'livres',
    schemaJson: schema,
    breadcrumbSchemaJson: breadcrumbSchema('Bibliothèque', `${BASE_URL}/livres.html`, title, canonical),
    body,
  });
}

/* ── Audios ──────────────────────────────────────────────────── */
function generateAudio(item) {
  const slug      = String(item.slug || item.id);
  const title     = item.title || 'Message audio';
  const series    = item.series || item.sectionName || '';
  const duration  = item.duration || '';
  const canonical = `${BASE_URL}/audios/${slug}.html`;

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'AudioObject',
    'name': title,
    'url': canonical,
    'inLanguage': 'fr',
    ...(duration ? { 'duration': duration } : {}),
    ...(item.src  ? { 'contentUrl': item.src } : {}),
    ...(series    ? { 'partOfSeries': { '@type': 'PodcastSeries', 'name': series } } : {}),
    'publisher': { '@type': 'Organization', 'name': SITE_NAME, 'url': BASE_URL },
  };

  const meta = [
    series   ? `<span>🎙 ${esc(series)}</span>`   : '',
    duration ? `<span>⏱ ${esc(duration)}</span>` : '',
  ].filter(Boolean).join('');

  const body = `${breadcrumb('audios.html', 'Messages audio', title)}
    <div class="detail-header">
      <span class="detail-header__type">Message audio</span>
      <h1 class="detail-header__title">${esc(title)}</h1>
      ${meta ? `<div class="detail-header__meta">${meta}</div>` : ''}
    </div>
    <div class="detail-actions">
      <a class="detail-btn detail-btn--primary" href="audios.html">
        <svg width="18" height="18" aria-hidden="true"><use href="#icon-audio"/></svg>
        Écouter sur la page audio
      </a>
    </div>
    <a class="detail-back" href="audios.html">← Tous les messages</a>`;

  return buildPage({
    slug, dir: 'audios', title, canonical,
    description: `Écouter "${title}"${series ? ` — ${series}` : ''}${duration ? ` (${duration})` : ''} sur ${SITE_NAME}.`,
    pageKey: 'audios',
    schemaJson: schema,
    breadcrumbSchemaJson: breadcrumbSchema('Messages audio', `${BASE_URL}/audios.html`, title, canonical),
    body,
  });
}

/* ── Articles ────────────────────────────────────────────────── */
function generateArticle(item) {
  const slug      = String(item.slug || item.id);
  const title     = item.title || 'Article';
  const cat       = item.cat   || '';
  const year      = item.year  || '';
  const canonical = `${BASE_URL}/articles/${slug}.html`;

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    'name': title,
    'headline': title,
    'url': canonical,
    'inLanguage': item.en ? 'en' : 'fr',
    ...(year ? { 'datePublished': String(year) } : {}),
    ...(cat  ? { 'keywords': cat } : {}),
    'publisher': { '@type': 'Organization', 'name': SITE_NAME, 'url': BASE_URL },
  };

  const meta = [
    cat  ? `<span>📂 ${esc(cat)}</span>`      : '',
    year ? `<span>📅 ${esc(String(year))}</span>` : '',
  ].filter(Boolean).join('');

  const actions = [
    item.epub ? `<a class="detail-btn detail-btn--primary" href="articles.html#article-${esc(item.id)}">
        <svg width="18" height="18" aria-hidden="true"><use href="#icon-livre"/></svg>
        Lire en ligne
      </a>` : '',
    item.pdf  ? `<a class="detail-btn detail-btn--secondary"
        href="${esc(item.pdf)}" target="_blank" rel="noopener noreferrer">
        Télécharger le PDF
      </a>` : '',
  ].filter(Boolean).join('\n      ');

  const body = `${breadcrumb('articles.html', 'Articles & Méditations', title)}
    <div class="detail-header">
      <span class="detail-header__type">Article</span>
      <h1 class="detail-header__title">${esc(title)}</h1>
      ${meta ? `<div class="detail-header__meta">${meta}</div>` : ''}
    </div>
    <div class="detail-actions">
      ${actions || `<a class="detail-btn detail-btn--secondary" href="articles.html">Retour aux articles</a>`}
    </div>
    <a class="detail-back" href="articles.html">← Tous les articles</a>`;

  return buildPage({
    slug, dir: 'articles', title, canonical,
    description: `Lire "${title}"${cat ? ` — ${cat}` : ''}${year ? ` (${year})` : ''} sur ${SITE_NAME}.`,
    pageKey: 'articles',
    schemaJson: schema,
    breadcrumbSchemaJson: breadcrumbSchema('Articles & Méditations', `${BASE_URL}/articles.html`, title, canonical),
    body,
  });
}

/* ── Vidéos ──────────────────────────────────────────────────── */
function generateVideo(item) {
  const slug      = String(item.slug || item.id);
  const title     = item.title    || 'Vidéo';
  const series    = item.series   || '';
  const ytId      = item.youtube_id || '';
  const canonical = `${BASE_URL}/videos/${slug}.html`;

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'VideoObject',
    'name': title,
    'url': canonical,
    'inLanguage': 'fr',
    ...(ytId ? {
      'embedUrl': `https://www.youtube.com/embed/${ytId}`,
      'thumbnailUrl': `https://img.youtube.com/vi/${ytId}/hqdefault.jpg`,
    } : {}),
    ...(series ? { 'partOfSeries': { '@type': 'VideoSeries', 'name': series } } : {}),
    'publisher': { '@type': 'Organization', 'name': SITE_NAME, 'url': BASE_URL },
  };

  const videoBlock = ytId
    ? `<div class="detail-video-wrapper">
      <iframe
        src="https://www.youtube.com/embed/${esc(ytId)}"
        title="${esc(title)}"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen
        loading="lazy">
      </iframe>
    </div>` : '';

  const meta = series ? `<div class="detail-header__meta"><span>🎞 ${esc(series)}</span></div>` : '';

  const body = `${breadcrumb('videos.html', 'Vidéos', title)}
    <div class="detail-header">
      <span class="detail-header__type">Vidéo</span>
      <h1 class="detail-header__title">${esc(title)}</h1>
      ${meta}
    </div>
    ${videoBlock}
    <a class="detail-back" href="videos.html">← Toutes les vidéos</a>`;

  const ogImage = ytId
    ? `https://img.youtube.com/vi/${ytId}/hqdefault.jpg`
    : undefined;

  return buildPage({
    slug, dir: 'videos', title, canonical, ogImage,
    description: `Regarder "${title}"${series ? ` — ${series}` : ''} sur ${SITE_NAME}.`,
    pageKey: 'videos',
    schemaJson: schema,
    breadcrumbSchemaJson: breadcrumbSchema('Vidéos', `${BASE_URL}/videos.html`, title, canonical),
    body,
  });
}

/* ── Podcasts ────────────────────────────────────────────────── */
function generatePodcast(item) {
  const slug      = String(item.slug || item.id);
  const title     = item.title || 'Podcast';
  const series    = item.series || item.sectionName || '';
  const duration  = item.duration || '';
  const canonical = `${BASE_URL}/podcasts/${slug}.html`;

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'PodcastEpisode',
    'name': title,
    'url': canonical,
    'inLanguage': 'fr',
    ...(duration ? { 'timeRequired': duration } : {}),
    ...(item.src  ? { 'associatedMedia': { '@type': 'AudioObject', 'contentUrl': item.src } } : {}),
    ...(series    ? { 'partOfSeries': { '@type': 'PodcastSeries', 'name': series } } : {}),
    'publisher': { '@type': 'Organization', 'name': SITE_NAME, 'url': BASE_URL },
  };

  const meta = [
    series   ? `<span>🎙 ${esc(series)}</span>`   : '',
    duration ? `<span>⏱ ${esc(duration)}</span>` : '',
  ].filter(Boolean).join('');

  const body = `${breadcrumb('podcasts.html', 'Séries podcast', title)}
    <div class="detail-header">
      <span class="detail-header__type">Podcast</span>
      <h1 class="detail-header__title">${esc(title)}</h1>
      ${meta ? `<div class="detail-header__meta">${meta}</div>` : ''}
    </div>
    <div class="detail-actions">
      <a class="detail-btn detail-btn--primary" href="podcasts.html">
        <svg width="18" height="18" aria-hidden="true"><use href="#icon-podcast"/></svg>
        Écouter sur la page podcasts
      </a>
    </div>
    <a class="detail-back" href="podcasts.html">← Tous les podcasts</a>`;

  return buildPage({
    slug, dir: 'podcasts', title, canonical,
    description: `Écouter "${title}"${series ? ` — ${series}` : ''}${duration ? ` (${duration})` : ''} sur ${SITE_NAME}.`,
    pageKey: 'podcasts',
    schemaJson: schema,
    breadcrumbSchemaJson: breadcrumbSchema('Séries podcast', `${BASE_URL}/podcasts.html`, title, canonical),
    body,
  });
}

/* ══════════════════════════════════════════════════════════════
   MISE À JOUR DU SITEMAP
══════════════════════════════════════════════════════════════ */
function buildSitemap(generatedUrls) {
  const staticUrls = [
    { loc: `${BASE_URL}/`,                          changefreq: 'weekly',  priority: '1.0' },
    { loc: `${BASE_URL}/radio.html`,                changefreq: 'daily',   priority: '0.9' },
    { loc: `${BASE_URL}/podcasts.html`,             changefreq: 'weekly',  priority: '0.8' },
    { loc: `${BASE_URL}/audios.html`,               changefreq: 'weekly',  priority: '0.8' },
    { loc: `${BASE_URL}/videos.html`,               changefreq: 'weekly',  priority: '0.8' },
    { loc: `${BASE_URL}/articles.html`,             changefreq: 'weekly',  priority: '0.7' },
    { loc: `${BASE_URL}/livres.html`,               changefreq: 'monthly', priority: '0.7' },
    { loc: `${BASE_URL}/louange.html`,              changefreq: 'weekly',  priority: '0.7' },
    { loc: `${BASE_URL}/nouveau.html`,              changefreq: 'monthly', priority: '0.6' },
    { loc: `${BASE_URL}/qui-sommes-nous.html`,      changefreq: 'monthly', priority: '0.5' },
    { loc: `${BASE_URL}/nospartenaires.html`,       changefreq: 'monthly', priority: '0.5' },
    { loc: `${BASE_URL}/confidentialite.html`,      changefreq: 'yearly',  priority: '0.3' },
  ];

  const allUrls = [
    ...staticUrls,
    ...generatedUrls.map(loc => ({ loc, changefreq: 'monthly', priority: '0.5' })),
  ];

  const urlElements = allUrls
    .map(u => `  <url><loc>${u.loc}</loc><changefreq>${u.changefreq}</changefreq><priority>${u.priority}</priority></url>`)
    .join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urlElements}
</urlset>
`;
}

/* ══════════════════════════════════════════════════════════════
   POINT D'ENTRÉE PRINCIPAL
══════════════════════════════════════════════════════════════ */
const configs = [
  { file: 'books.json',    dir: 'livres',   fn: generateBook    },
  { file: 'audios.json',   dir: 'audios',   fn: generateAudio   },
  { file: 'articles.json', dir: 'articles', fn: generateArticle },
  { file: 'videos.json',   dir: 'videos',   fn: generateVideo   },
  { file: 'podcasts.json', dir: 'podcasts', fn: generatePodcast },
];

let totalGenerated  = 0;
let totalErrors     = 0;
const generatedUrls = [];

for (const { file, dir, fn } of configs) {
  let items;
  try {
    items = loadJson(file);
  } catch (e) {
    console.error(`❌ Impossible de lire ${file} :`, e.message);
    totalErrors++;
    continue;
  }

  const outDir = join(ROOT, dir);
  if (!DRY_RUN) ensureDir(outDir);

  let count = 0;
  for (const item of items) {
    const slug = String(item.slug || item.id);
    if (!slug) { console.warn(`⚠️  Item sans slug dans ${file} :`, item); continue; }

    try {
      const html = fn(item);
      const outPath = join(outDir, `${slug}.html`);
      const url     = `${BASE_URL}/${dir}/${slug}.html`;

      if (DRY_RUN) {
        console.log(`  [dry] ${dir}/${slug}.html → ${url}`);
      } else {
        writeFileSync(outPath, html, 'utf8');
      }

      generatedUrls.push(url);
      count++;
    } catch (e) {
      console.error(`❌ Erreur sur ${dir}/${slug} :`, e.message);
      totalErrors++;
    }
  }

  console.log(`✅ ${dir} : ${count} pages générées`);
  totalGenerated += count;
}

/* ── Sitemap ─────────────────────────────────────────────────── */
const sitemapPath = join(ROOT, 'sitemap.xml');
const sitemapXml  = buildSitemap(generatedUrls);
if (!DRY_RUN) {
  writeFileSync(sitemapPath, sitemapXml, 'utf8');
  console.log(`✅ sitemap.xml mis à jour (${12 + generatedUrls.length} URLs)`);
} else {
  console.log(`[dry] sitemap.xml contiendrait ${12 + generatedUrls.length} URLs`);
}

console.log(`\n📄 Total : ${totalGenerated} pages générées, ${totalErrors} erreurs.`);
if (totalErrors > 0) process.exit(1);
