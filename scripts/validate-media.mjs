#!/usr/bin/env node
/**
 * validate-media.mjs
 * Vérifie que tous les fichiers EPUB, PDF et MP3 référencés dans le site existent.
 * Rapport : OK, MANQUANT, ERREUR pour chaque fichier.
 *
 * Usage : node scripts/validate-media.mjs
 */

import fs   from 'fs';
import path from 'path';
import http from 'http';
import https from 'https';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT      = path.resolve(__dirname, '..');

/* ── Couleurs console ──────────────────────────────────────── */
const C = {
  ok    : '\x1b[32m✓\x1b[0m',
  err   : '\x1b[31m✗\x1b[0m',
  warn  : '\x1b[33m⚠\x1b[0m',
  reset : '\x1b[0m',
  bold  : '\x1b[1m',
  dim   : '\x1b[2m',
};

const results = { ok: 0, missing: 0, errors: 0, skipped: 0 };

/* ── Vérification fichier local ────────────────────────────── */
function checkLocal(relPath, source) {
  const absPath = path.join(ROOT, relPath);
  const exists  = fs.existsSync(absPath);
  if (exists) {
    const size = fs.statSync(absPath).size;
    console.log(`${C.ok} LOCAL  ${relPath} ${C.dim}(${(size / 1024 / 1024).toFixed(1)} MB) ← ${source}${C.reset}`);
    results.ok++;
  } else {
    console.log(`${C.err} MANQUANT  ${relPath} ${C.dim}← ${source}${C.reset}`);
    results.missing++;
  }
}

/* ── Vérification URL externe (HEAD request) ───────────────── */
function checkUrl(url, source) {
  return new Promise((resolve) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.request(url, { method: 'HEAD', timeout: 10000 }, (res) => {
      const code = res.statusCode;
      if (code >= 200 && code < 400) {
        console.log(`${C.ok} URL ${code}  ${url} ${C.dim}← ${source}${C.reset}`);
        results.ok++;
      } else {
        console.log(`${C.err} URL ${code}  ${url} ${C.dim}← ${source}${C.reset}`);
        results.errors++;
      }
      resolve();
    });
    req.on('error', (e) => {
      console.log(`${C.err} URL ERR  ${url} ${C.dim}(${e.message}) ← ${source}${C.reset}`);
      results.errors++;
      resolve();
    });
    req.on('timeout', () => {
      req.destroy();
      console.log(`${C.warn} URL TIMEOUT  ${url} ${C.dim}← ${source}${C.reset}`);
      results.errors++;
      resolve();
    });
    req.end();
  });
}

/* ── Extraction des références depuis les fichiers HTML ────── */
function extractFromHtml(filename) {
  const filePath = path.join(ROOT, filename);
  if (!fs.existsSync(filePath)) return [];
  const content = fs.readFileSync(filePath, 'utf-8');
  const refs = [];

  /* EPUB : href="assets/books/..." ou data-epub="..." */
  const epubRe = /(?:href|data-epub|src)="([^"]*\.epub)"/g;
  for (const m of content.matchAll(epubRe)) {
    refs.push({ type: 'epub', path: m[1], source: filename });
  }

  /* PDF : href="...\.pdf" */
  const pdfRe = /href="([^"]*\.pdf)"/g;
  for (const m of content.matchAll(pdfRe)) {
    refs.push({ type: 'pdf', path: m[1], source: filename });
  }

  /* MP3 local : src="assets/audio/..." */
  const mp3Re = /(?:src|data-src)="(assets\/audio\/[^"]*\.mp3)"/g;
  for (const m of content.matchAll(mp3Re)) {
    refs.push({ type: 'mp3', path: m[1], source: filename });
  }

  return refs;
}

/* ── Extraction depuis les JSON de données ─────────────────── */
function extractFromJson(filename, fields) {
  const filePath = path.join(ROOT, 'assets/data', filename);
  if (!fs.existsSync(filePath)) {
    console.log(`${C.warn} JSON ABSENT  assets/data/${filename}`);
    return [];
  }
  let data;
  try {
    data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  } catch (e) {
    console.log(`${C.err} JSON INVALIDE  assets/data/${filename}: ${e.message}`);
    results.errors++;
    return [];
  }

  const items = Array.isArray(data) ? data : (data.items || data.books || data.audios || []);
  const refs = [];

  for (const item of items) {
    for (const field of fields) {
      const val = item[field];
      if (!val) continue;
      if (val.startsWith('http')) {
        refs.push({ type: field, url: val, source: `${filename}[${item.id || item.title}]` });
      } else {
        refs.push({ type: field, path: val, source: `${filename}[${item.id || item.title}]` });
      }
    }
  }
  return refs;
}

/* ── Main ──────────────────────────────────────────────────── */
async function main() {
  console.log(`\n${C.bold}══ Validation des médias — L'Évangile du Royaume ══${C.reset}\n`);

  const allRefs = [];

  /* Extraire depuis les pages HTML */
  for (const page of ['livres.html', 'articles.html', 'audios.html', 'podcasts.html']) {
    allRefs.push(...extractFromHtml(page));
  }

  /* Extraire depuis les JSON (si déjà migrés) */
  allRefs.push(...extractFromJson('books.json',    ['epub', 'pdf']));
  allRefs.push(...extractFromJson('articles.json', ['epub', 'pdf']));
  allRefs.push(...extractFromJson('audios.json',   ['source_url', 'fallback_url']));
  allRefs.push(...extractFromJson('podcasts.json', ['source_url', 'fallback_url']));

  /* Dédupliquer */
  const seen = new Set();
  const unique = allRefs.filter(r => {
    const key = r.path || r.url;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  if (unique.length === 0) {
    console.log(`${C.warn} Aucune référence trouvée. Les JSON de données ne sont pas encore créés.\n`);
    process.exit(0);
  }

  console.log(`${C.dim}${unique.length} référence(s) à vérifier…${C.reset}\n`);

  /* Séparer local / externe */
  const localRefs   = unique.filter(r => r.path && !r.path.startsWith('http'));
  const externalRefs = unique.filter(r => r.url || (r.path && r.path.startsWith('http')));

  /* --- Fichiers locaux (synchrones) --- */
  if (localRefs.length) {
    console.log(`${C.bold}── Fichiers locaux (${localRefs.length}) ────────────────────────${C.reset}`);
    for (const ref of localRefs) {
      const p = ref.path.startsWith('/') ? ref.path.slice(1) : ref.path;
      checkLocal(p, ref.source);
    }
    console.log('');
  }

  /* --- URLs externes (asynchrones, 5 à la fois) --- */
  if (externalRefs.length) {
    console.log(`${C.bold}── URLs externes (${externalRefs.length}) ─────────────────────────${C.reset}`);
    console.log(`${C.dim}(Google Drive est souvent bloqué par les requêtes HEAD — skipped si erreur)${C.reset}\n`);
    const CONCURRENCY = 5;
    for (let i = 0; i < externalRefs.length; i += CONCURRENCY) {
      const batch = externalRefs.slice(i, i + CONCURRENCY);
      await Promise.all(batch.map(ref => checkUrl(ref.url || ref.path, ref.source)));
    }
    console.log('');
  }

  /* --- Résumé --- */
  const total = results.ok + results.missing + results.errors;
  console.log(`${C.bold}══ Résumé ══${C.reset}`);
  console.log(`  ${C.ok} OK      : ${results.ok}`);
  console.log(`  ${C.err} Manquants : ${results.missing}`);
  console.log(`  ${C.err} Erreurs   : ${results.errors}`);
  console.log(`  Total   : ${total}\n`);

  if (results.missing > 0 || results.errors > 0) {
    process.exit(1);
  }
}

main().catch(err => { console.error(err); process.exit(1); });
