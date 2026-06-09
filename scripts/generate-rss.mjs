#!/usr/bin/env node
/* ============================================================
   scripts/generate-rss.mjs
   Génère podcast.xml — flux RSS 2.0 compatible iTunes/Spotify/Apple Podcasts.

   Usage :
     node scripts/generate-rss.mjs

   Sortie :
     podcast.xml — à la racine du site (accessible via /podcast.xml)

   Distributable sur :
     - Apple Podcasts  (itunes:)
     - Spotify
     - Deezer
     - Pocket Casts
     - Google Podcasts (deprecated mais compatible)

   Source : assets/data/podcasts.json
   ============================================================ */

import { readFileSync, writeFileSync } from 'fs';
import { join, dirname }                from 'path';
import { fileURLToPath }                from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT      = join(__dirname, '..');

const BASE_URL   = 'https://levangileduroyaume.com';
const SITE_NAME  = "L'Évangile du Royaume";
const FEED_DESC  = "Enseignements bibliques de L'Évangile du Royaume — prophétie, eschatologie, vie chrétienne et ministère.";
const FEED_EMAIL = 'nousecrire@levangileduroyaume.com';
const FEED_IMG   = `${BASE_URL}/assets/images/og-default.png`;

/* ── Lire les données ────────────────────────────────────────── */
const raw      = readFileSync(join(ROOT, 'assets', 'data', 'podcasts.json'), 'utf8');
const podcasts = Object.values(JSON.parse(raw));

if (!podcasts.length) {
  console.error('❌ Aucun podcast trouvé dans podcasts.json');
  process.exit(1);
}

/* ── Échapper le XML ─────────────────────────────────────────── */
function escXml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&apos;');
}

/* ── Convertir durée "h:mm:ss" ou "mm:ss" en secondes ────────── */
function durationToSeconds(dur) {
  if (!dur) return 0;
  const parts = dur.split(':').map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

/* ── Générer une date de publication (1 épisode / semaine, du plus récent) */
function buildPubDate(index, total) {
  /* Date de base : Jan 1 2024, reculer de (total - index) semaines */
  const base = new Date('2024-01-01T10:00:00Z');
  base.setDate(base.getDate() - (total - 1 - index) * 7);
  return base.toUTCString();
}

/* ── Générer chaque <item> ───────────────────────────────────── */
function buildItem(item, index, total) {
  const title    = item.title || 'Épisode sans titre';
  const slug     = String(item.slug || item.id);
  const series   = item.series || item.sectionName || SITE_NAME;
  const src      = item.src || '';
  const duration = item.duration || '';
  const guid     = `${BASE_URL}/podcasts/${slug}.html`;
  const pubDate  = buildPubDate(index, total);
  const durSec   = durationToSeconds(duration);

  return `    <item>
      <title>${escXml(title)}</title>
      <itunes:title>${escXml(title)}</itunes:title>
      <description>${escXml(title)} — Série : ${escXml(series)}. Enseignement biblique de ${escXml(SITE_NAME)}.</description>
      <itunes:summary>${escXml(title)} — Série : ${escXml(series)}.</itunes:summary>
      <itunes:subtitle>${escXml(series)}</itunes:subtitle>
      <link>${guid}</link>
      <guid isPermaLink="true">${guid}</guid>
      <pubDate>${pubDate}</pubDate>
      ${src ? `<enclosure url="${escXml(src)}" type="audio/mpeg" length="0"/>` : '<!-- pas de source MP3 -->'}
      ${duration ? `<itunes:duration>${escXml(duration)}</itunes:duration>` : ''}
      ${durSec   ? `<itunes:duration>${durSec}</itunes:duration>` : ''}
      <itunes:episodeType>full</itunes:episodeType>
    </item>`;
}

/* ── Construire le flux complet ──────────────────────────────── */
const total   = podcasts.length;
const items   = podcasts
  .map((item, i) => buildItem(item, i, total))
  .join('\n');

const lastBuildDate = new Date().toUTCString();

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<!-- ════════════════════════════════════════════════════════════
     podcast.xml — Flux RSS L'Évangile du Royaume
     Généré automatiquement par scripts/generate-rss.mjs
     NE PAS MODIFIER MANUELLEMENT — relancer le script à la place
     ════════════════════════════════════════════════════════════ -->
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:content="http://purl.org/rss/1.0/modules/content/"
  xmlns:atom="http://www.w3.org/2005/Atom">

  <channel>
    <title>${escXml(SITE_NAME)}</title>
    <link>${BASE_URL}/podcasts.html</link>
    <description>${escXml(FEED_DESC)}</description>
    <language>fr</language>
    <lastBuildDate>${lastBuildDate}</lastBuildDate>
    <atom:link href="${BASE_URL}/podcast.xml" rel="self" type="application/rss+xml"/>

    <itunes:author>${escXml(SITE_NAME)}</itunes:author>
    <itunes:owner>
      <itunes:name>${escXml(SITE_NAME)}</itunes:name>
      <itunes:email>${FEED_EMAIL}</itunes:email>
    </itunes:owner>
    <itunes:image href="${FEED_IMG}"/>
    <image>
      <url>${FEED_IMG}</url>
      <title>${escXml(SITE_NAME)}</title>
      <link>${BASE_URL}/podcasts.html</link>
    </image>
    <itunes:category text="Religion &amp; Spirituality">
      <itunes:category text="Christianity"/>
    </itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <copyright>© ${new Date().getFullYear()} ${escXml(SITE_NAME)}</copyright>

${items}

  </channel>
</rss>
`;

const outPath = join(ROOT, 'podcast.xml');
writeFileSync(outPath, xml, 'utf8');
console.log(`✅ podcast.xml généré : ${podcasts.length} épisodes, ${Math.round(xml.length / 1024)} Ko`);
