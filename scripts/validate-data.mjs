#!/usr/bin/env node
/**
 * scripts/validate-data.mjs
 * Validation automatique des fichiers JSON du site L'Évangile du Royaume.
 *
 * Contrôles effectués :
 *   1. Syntaxe JSON valide pour chaque fichier assets/data/
 *   2. Champs requis présents et non vides pour chaque schéma
 *   3. IDs uniques au sein de chaque fichier
 *   4. Fichiers EPUB locaux présents sur disque
 *   5. HEAD request sur les URLs PDF/MP3 externes (sauf --quick)
 *   6. Icônes SVG — tout href="#icon-xxx" dans les HTML a un <symbol> dans nav.js
 *
 * Usage :
 *   node scripts/validate-data.mjs           # validation complète (HTTP inclus)
 *   node scripts/validate-data.mjs --quick   # sans requêtes HTTP
 *   node scripts/validate-data.mjs --file books.json  # un seul fichier
 *
 * Codes de sortie :
 *   0 — tout OK (erreurs 0, warnings possibles)
 *   1 — au moins une erreur
 */

import fs   from 'fs';
import path from 'path';
import http  from 'http';
import https from 'https';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

/* ── Options ───────────────────────────────────────────────────── */
const ARGS  = process.argv.slice(2);
const QUICK = ARGS.includes('--quick');
const FILE_FILTER = (() => {
  const idx = ARGS.indexOf('--file');
  return idx !== -1 ? ARGS[idx + 1] : null;
})();

/* ── Couleurs console ──────────────────────────────────────────── */
const C = {
  ok   : '\x1b[32m✓\x1b[0m',
  err  : '\x1b[31m✗\x1b[0m',
  warn : '\x1b[33m⚠\x1b[0m',
  info : '\x1b[36m·\x1b[0m',
  bold : '\x1b[1m',
  dim  : '\x1b[2m',
  reset: '\x1b[0m',
};

/* ── Compteurs globaux ─────────────────────────────────────────── */
const counts = { errors: 0, warnings: 0, ok: 0, skipped: 0 };

function logOk(msg)   { counts.ok++;       console.log(`  ${C.ok}  ${msg}`); }
function logErr(msg)  { counts.errors++;   console.error(`  ${C.err}  ${C.bold}ERREUR${C.reset} ${msg}`); }
function logWarn(msg) { counts.warnings++; console.warn(`  ${C.warn}  ${msg}`); }
function logInfo(msg) {                    console.log(`  ${C.info}  ${C.dim}${msg}${C.reset}`); }
function section(title) { console.log(`\n${C.bold}── ${title}${C.reset}`); }

/* ═══════════════════════════════════════════════════════════════
   1. SCHÉMAS — champs requis par type de fichier
   ═══════════════════════════════════════════════════════════════ */
const SCHEMAS = {
  'books.json': {
    required: ['id', 'title', 'slug', 'type', 'source', 'color', 'tags', 'epub'],
    rules: [
      { name: 'tags doit être un tableau',        fn: item => Array.isArray(item.tags) },
      { name: 'epub doit être une chaîne',        fn: item => typeof item.epub === 'string' },
      { name: 'color doit être un entier 1-8',    fn: item => Number.isInteger(item.color) && item.color >= 1 && item.color <= 8 },
    ],
    mediaFields: [
      { field: 'epub', kind: 'local' },
      { field: 'pdf',  kind: 'remote', optional: true },
    ],
  },
  'audios.json': {
    required: ['id', 'title', 'slug', 'type', 'source', 'series', 'sectionName', 'src'],
    rules: [
      { name: 'src doit être une URL',            fn: item => typeof item.src === 'string' && item.src.startsWith('http') },
    ],
    mediaFields: [
      { field: 'src', kind: 'remote' },
    ],
  },
  'podcasts.json': {
    required: ['id', 'title', 'slug', 'type', 'source', 'series', 'sectionName', 'src'],
    rules: [
      { name: 'src doit être une URL',            fn: item => typeof item.src === 'string' && item.src.startsWith('http') },
    ],
    mediaFields: [
      { field: 'src', kind: 'remote' },
    ],
  },
  'videos.json': {
    required: ['id', 'title', 'slug', 'type', 'source', 'youtube_id', 'series'],
    rules: [
      { name: 'youtube_id doit être 11 caractères', fn: item => /^[a-zA-Z0-9_-]{11}$/.test(item.youtube_id) },
    ],
    /* kind 'youtube' → vérification via oEmbed (hors --quick) */
    mediaFields: [
      { field: 'youtube_id', kind: 'youtube' },
    ],
  },
  'articles.json': {
    required: ['id', 'title', 'slug', 'type', 'source', 'color', 'cat', 'year'],
    rules: [
      { name: 'year doit être un entier', fn: item => Number.isInteger(item.year) },
    ],
    mediaFields: [
      { field: 'epub', kind: 'local',  optional: true },
      { field: 'pdf',  kind: 'remote', optional: true },
    ],
  },
  'louange.json': {
    required: ['id', 'title', 'type', 'source'],
    rules: [
      { name: 'type doit être "yt" ou "drive"', fn: item => item.type === 'yt' || item.type === 'drive' },
      { name: 'source doit être une chaîne non vide', fn: item => typeof item.source === 'string' && item.source.length > 0 },
    ],
    mediaFields: [],
  },
  'partners.json': {
    required: ['id', 'name', 'type', 'url', 'label', 'color_start', 'color_end', 'initial'],
    rules: [
      { name: 'url doit commencer par https://', fn: item => typeof item.url === 'string' && item.url.startsWith('https://') },
    ],
    mediaFields: [],
  },
  'radio-schedule.json': {
    required: ['id', 'time', 'name', 'desc'],
    rules: [],
    mediaFields: [],
  },
};

/* ═══════════════════════════════════════════════════════════════
   2. UTILITAIRES RÉSEAU
   ═══════════════════════════════════════════════════════════════ */

/**
 * HEAD request sur une URL externe.
 * Retourne { ok: true } ou { ok: false, status, error }
 */
function headRequest(url, timeout = 8000) {
  return new Promise(resolve => {
    const client = url.startsWith('https://') ? https : http;
    let parsed;
    try { parsed = new URL(url); } catch { resolve({ ok: false, error: 'URL invalide' }); return; }

    const req = client.request(
      { method: 'HEAD', hostname: parsed.hostname, path: parsed.pathname + parsed.search, port: parsed.port || undefined },
      res => {
        const { statusCode } = res;
        res.resume();
        if (statusCode >= 200 && statusCode < 400) {
          resolve({ ok: true, status: statusCode });
        } else {
          resolve({ ok: false, status: statusCode });
        }
      }
    );
    req.setTimeout(timeout, () => { req.destroy(); resolve({ ok: false, error: `timeout ${timeout}ms` }); });
    req.on('error', err => resolve({ ok: false, error: err.message }));
    req.end();
  });
}

/**
 * Vérifie qu'un ID YouTube est accessible via l'API oEmbed.
 * Retourne { ok: true } ou { ok: false, error }
 * Codes : 200 = public, 401 = privée, 404 = supprimée/introuvable
 */
function checkYouTubeId(ytId, timeout = 8000) {
  const url = 'https://www.youtube.com/oembed?url=' +
              encodeURIComponent('https://www.youtube.com/watch?v=' + ytId) +
              '&format=json';
  return new Promise(resolve => {
    let parsed;
    try { parsed = new URL(url); } catch { resolve({ ok: false, error: 'URL invalide' }); return; }
    const req = https.request(
      { method: 'GET', hostname: parsed.hostname, path: parsed.pathname + parsed.search },
      res => {
        res.resume(); /* drainer immédiatement */
        const s = res.statusCode;
        if (s === 200)      resolve({ ok: true,  status: s });
        else if (s === 401) resolve({ ok: false, error: 'vidéo privée ou non listée' });
        else if (s === 404) resolve({ ok: false, error: 'vidéo supprimée ou introuvable' });
        else                resolve({ ok: false, error: `HTTP ${s}` });
      }
    );
    req.setTimeout(timeout, () => { req.destroy(); resolve({ ok: false, error: `timeout ${timeout}ms` }); });
    req.on('error', err => resolve({ ok: false, error: err.message }));
    req.end();
  });
}

/* ═══════════════════════════════════════════════════════════════
   3. VALIDATION D'UN FICHIER JSON
   ═══════════════════════════════════════════════════════════════ */

async function validateFile(filename) {
  section(`${filename}`);

  const filePath = path.join(ROOT, 'assets', 'data', filename);

  /* 3a. Syntaxe JSON ─────────────────────────────────────────── */
  let data;
  try {
    const raw = fs.readFileSync(filePath, 'utf8');
    data = JSON.parse(raw);
    logOk(`Syntaxe JSON valide`);
  } catch (e) {
    logErr(`JSON invalide : ${e.message}`);
    return; /* Arrêt immédiat — les autres checks seraient invalides */
  }

  if (!Array.isArray(data)) {
    logErr(`La racine doit être un tableau JSON, reçu : ${typeof data}`);
    return;
  }

  logOk(`${data.length} élément(s)`);

  const schema = SCHEMAS[filename];
  if (!schema) {
    logWarn(`Aucun schéma défini pour ${filename} — validation de structure ignorée`);
    return;
  }

  /* 3b. IDs uniques ─────────────────────────────────────────── */
  const ids = data.map(item => item.id);
  const dupIds = ids.filter((id, i) => ids.indexOf(id) !== i);
  if (dupIds.length > 0) {
    logErr(`IDs dupliqués : ${dupIds.join(', ')}`);
  } else {
    logOk(`IDs uniques`);
  }

  /* 3c. Champs requis ────────────────────────────────────────── */
  let fieldErrors = 0;
  data.forEach(item => {
    schema.required.forEach(field => {
      const val = item[field];
      const empty = val === undefined || val === null || val === '';
      if (empty) {
        logErr(`[id:${item.id}] champ requis manquant ou vide : "${field}"`);
        fieldErrors++;
      }
    });
  });
  if (fieldErrors === 0) {
    logOk(`Champs requis présents sur ${data.length} éléments`);
  }

  /* 3d. Règles métier ────────────────────────────────────────── */
  schema.rules.forEach(rule => {
    let ruleErrors = 0;
    data.forEach(item => {
      try {
        if (!rule.fn(item)) {
          logWarn(`[id:${item.id}] règle non respectée : ${rule.name}`);
          ruleErrors++;
        }
      } catch (e) {
        logWarn(`[id:${item.id}] erreur lors de la règle "${rule.name}" : ${e.message}`);
        ruleErrors++;
      }
    });
    if (ruleErrors === 0) logOk(`Règle OK : ${rule.name}`);
  });

  /* 3e. Médias ───────────────────────────────────────────────── */
  if (schema.mediaFields.length === 0) return;

  const mediaItems = [];
  data.forEach(item => {
    schema.mediaFields.forEach(mf => {
      const val = item[mf.field];
      if (!val) {
        if (!mf.optional) logWarn(`[id:${item.id}] champ media "${mf.field}" absent ou vide`);
        return;
      }
      mediaItems.push({ id: item.id, field: mf.field, val, kind: mf.kind });
    });
  });

  /* 3e-i. Fichiers locaux (EPUB) ─────────────────────────────── */
  const localItems = mediaItems.filter(m => m.kind === 'local');
  localItems.forEach(m => {
    const localPath = path.join(ROOT, m.val);
    if (!fs.existsSync(localPath)) {
      logErr(`[id:${m.id}] fichier local introuvable : ${m.val}`);
    } else {
      counts.ok++;
    }
  });

  const localOkCount = localItems.filter(m => fs.existsSync(path.join(ROOT, m.val))).length;
  if (localItems.length > 0) {
    logOk(`Fichiers locaux présents : ${localOkCount}/${localItems.length}`);
  }

  /* 3e-ii. URLs distantes (PDF, MP3) + IDs YouTube — ignorés si --quick */
  const remoteItems = mediaItems.filter(m => m.kind === 'remote' || m.kind === 'youtube');
  if (remoteItems.length === 0) return;

  if (QUICK) {
    const ytCount   = remoteItems.filter(m => m.kind === 'youtube').length;
    const restCount = remoteItems.length - ytCount;
    const labels = [
      restCount > 0 ? `${restCount} URL(s) distante(s)` : '',
      ytCount   > 0 ? `${ytCount} ID(s) YouTube`       : '',
    ].filter(Boolean).join(', ');
    logInfo(`--quick : ${labels} ignoré(s)`);
    counts.skipped += remoteItems.length;
    return;
  }

  const ytItems   = remoteItems.filter(m => m.kind === 'youtube');
  const restItems = remoteItems.filter(m => m.kind !== 'youtube');
  if (restItems.length > 0) logInfo(`Vérification de ${restItems.length} URL(s) distante(s)…`);
  if (ytItems.length  > 0) logInfo(`Vérification de ${ytItems.length} ID(s) YouTube via oEmbed…`);

  /* Requêtes en parallèle par lots de 5 */
  const BATCH = 5;
  let remoteOk = 0, remoteFail = 0;
  for (let i = 0; i < remoteItems.length; i += BATCH) {
    const batch = remoteItems.slice(i, i + BATCH);
    const results = await Promise.all(batch.map(m =>
      m.kind === 'youtube' ? checkYouTubeId(m.val) : headRequest(m.val)
    ));
    results.forEach((res, j) => {
      const m = batch[j];
      if (res.ok) {
        remoteOk++;
        counts.ok++;
      } else {
        remoteFail++;
        const detail = res.error || `HTTP ${res.status}`;
        const ref = m.kind === 'youtube' ? `https://youtu.be/${m.val}` : m.val;
        logWarn(`[id:${m.id}] ${m.field} inaccessible (${detail}) : ${ref}`);
      }
    });
  }
  if (remoteFail === 0) {
    logOk(`URLs distantes / IDs YouTube accessibles : ${remoteOk}/${remoteItems.length}`);
  }
}

/* ═══════════════════════════════════════════════════════════════
   4. VALIDATION DES ICÔNES SVG
   ═══════════════════════════════════════════════════════════════ */

function validateSvgIcons() {
  section('Icônes SVG — cohérence sprite vs HTML');

  /* Icônes définies dans nav.js (le sprite est injecté par nav.js) */
  const navJsPath = path.join(ROOT, 'assets', 'js', 'nav.js');
  let navJs;
  try {
    navJs = fs.readFileSync(navJsPath, 'utf8');
  } catch {
    logErr(`nav.js introuvable : ${navJsPath}`);
    return;
  }

  const defined = new Set(
    [...navJs.matchAll(/\bid=['"](icon-[^'"]+)['"]/g)].map(m => m[1])
  );
  logOk(`${defined.size} symbole(s) défini(s) dans le sprite (nav.js)`);

  /* Icônes utilisées dans tous les HTML */
  const htmlFiles = fs.readdirSync(ROOT).filter(f => f.endsWith('.html'));
  /* Également les JS qui construisent du HTML */
  const jsAssets = ['assets/js/nav.js', 'assets/js/modal-player.js',
                    'assets/js/video-renderer.js', 'assets/js/book-catalogue.js']
    .map(p => path.join(ROOT, p));

  const used = new Set();
  [...htmlFiles.map(f => path.join(ROOT, f)), ...jsAssets].forEach(fp => {
    if (!fs.existsSync(fp)) return;
    const content = fs.readFileSync(fp, 'utf8');
    [...content.matchAll(/href=['"](#)(icon-[^'"]+)['"]/g)].forEach(m => used.add(m[2]));
    /* use href sans # (inline SVG) */
    [...content.matchAll(/href=['"]#(icon-[^'"]+)['"]/g)].forEach(m => used.add(m[1]));
  });

  const missing = [...used].filter(id => !defined.has(id));
  const unused  = [...defined].filter(id => !used.has(id));

  if (missing.length > 0) {
    missing.forEach(id => logErr(`Icône utilisée mais non définie dans le sprite : #${id}`));
  } else {
    logOk(`Toutes les icônes utilisées (${used.size}) sont définies dans le sprite`);
  }

  if (unused.length > 0) {
    unused.forEach(id => logInfo(`Icône définie mais inutilisée : #${id}`));
  }
}

/* ═══════════════════════════════════════════════════════════════
   5. POINT D'ENTRÉE
   ═══════════════════════════════════════════════════════════════ */

async function main() {
  console.log(`\n${C.bold}╔══════════════════════════════════════════════════╗`);
  console.log(`║   validate-data.mjs — L'Évangile du Royaume     ║`);
  if (QUICK) {
    console.log(`║   Mode : --quick (requêtes HTTP désactivées)     ║`);
  }
  console.log(`╚══════════════════════════════════════════════════╝${C.reset}\n`);

  const dataDir = path.join(ROOT, 'assets', 'data');
  let filesToCheck = Object.keys(SCHEMAS);

  if (FILE_FILTER) {
    filesToCheck = filesToCheck.filter(f => f === FILE_FILTER);
    if (filesToCheck.length === 0) {
      console.error(`Fichier inconnu : ${FILE_FILTER}`);
      console.error(`Fichiers disponibles : ${Object.keys(SCHEMAS).join(', ')}`);
      process.exit(1);
    }
  }

  /* Vérifier que assets/data/ existe */
  if (!fs.existsSync(dataDir)) {
    logErr(`Dossier assets/data/ introuvable : ${dataDir}`);
    process.exit(1);
  }

  /* Valider chaque fichier JSON */
  for (const filename of filesToCheck) {
    const filePath = path.join(dataDir, filename);
    if (!fs.existsSync(filePath)) {
      section(filename);
      logErr(`Fichier introuvable : assets/data/${filename}`);
      continue;
    }
    await validateFile(filename);
  }

  /* Valider les icônes SVG (sauf si on filtre sur un seul fichier) */
  if (!FILE_FILTER) {
    validateSvgIcons();
  }

  /* ── Rapport final ──────────────────────────────────────────── */
  console.log(`\n${C.bold}── Résumé ──────────────────────────────────────${C.reset}`);
  console.log(`  ${C.ok}  OK       : ${counts.ok}`);
  if (counts.warnings > 0)
    console.log(`  ${C.warn}  Warnings : ${counts.warnings}`);
  if (counts.skipped > 0)
    console.log(`  ${C.info}  Ignorés  : ${counts.skipped} (--quick)`);
  if (counts.errors > 0) {
    console.log(`  ${C.err}  Erreurs  : ${counts.errors}`);
    console.log(`\n${C.bold}Résultat : ÉCHEC${C.reset} — ${counts.errors} erreur(s) à corriger.\n`);
    process.exit(1);
  } else {
    console.log(`\n${C.bold}Résultat : ${C.ok} SUCCÈS${C.reset}${counts.warnings > 0 ? ` (${counts.warnings} warning(s) non bloquant(s))` : ''}\n`);
    process.exit(0);
  }
}

main().catch(err => {
  console.error(`\nErreur inattendue : ${err.message}`);
  process.exit(1);
});
