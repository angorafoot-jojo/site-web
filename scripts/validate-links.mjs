#!/usr/bin/env node
/**
 * scripts/validate-links.mjs
 * Vérifie que tous les liens internes HTML des pages du site pointent vers des fichiers existants.
 *
 * Contrôles effectués :
 *   1. Parcourt tous les fichiers *.html à la racine du projet
 *   2. Extrait chaque href="*.html" et href="assets/..." (CSS, JS, JSON, images)
 *   3. Vérifie que le fichier cible existe sur disque
 *   4. Signale les liens cassés avec le fichier source et la cible manquante
 *
 * Usage :
 *   node scripts/validate-links.mjs           # vérifie tous les fichiers HTML
 *   node scripts/validate-links.mjs --verbose # affiche aussi les liens OK
 *
 * Codes de sortie :
 *   0 — aucun lien cassé
 *   1 — au moins un lien cassé
 */

import fs   from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT      = path.resolve(__dirname, '..');
const ARGS      = process.argv.slice(2);
const VERBOSE   = ARGS.includes('--verbose');

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

const counts = { ok: 0, broken: 0, skipped: 0 };

/* ── Extraire les liens internes d'un fichier HTML ─────────────── */
function extractInternalLinks(html, sourceFile) {
  const links = [];

  /* href="*.html" — liens vers d'autres pages */
  const hrefHtml = /href="([^"#?]+\.html)"/g;
  let m;
  while ((m = hrefHtml.exec(html)) !== null) {
    const target = m[1];
    /* Ignorer les URLs absolues */
    if (target.startsWith('http://') || target.startsWith('https://')) continue;
    links.push({ type: 'page', target });
  }

  /* href="assets/css/...", href="assets/js/...", src="assets/..." */
  const assetRe = /(href|src)="(assets\/[^"?#]+)"/g;
  while ((m = assetRe.exec(html)) !== null) {
    const target = m[2];
    links.push({ type: 'asset', target });
  }

  /* <link rel="canonical" href="..."> — ignorer (URL absolue) */
  /* <script src="assets/..."> */
  const scriptRe = /src="(assets\/[^"?#]+)"/g;
  while ((m = scriptRe.exec(html)) !== null) {
    const target = m[1];
    /* Éviter les doublons avec assetRe */
    if (!links.find(l => l.target === target)) {
      links.push({ type: 'asset', target });
    }
  }

  return links;
}

/* ── Vérifier un lien ──────────────────────────────────────────── */
function checkLink(sourceFile, link) {
  /* Résoudre le chemin relatif depuis la racine du site */
  const absTarget = path.resolve(ROOT, link.target);
  const exists    = fs.existsSync(absTarget);
  const rel       = path.relative(ROOT, sourceFile);

  if (exists) {
    counts.ok++;
    if (VERBOSE) {
      console.log(`  ${C.ok}  ${C.dim}${rel}${C.reset} → ${link.target}`);
    }
  } else {
    counts.broken++;
    console.error(`  ${C.err}  ${C.bold}LIEN CASSÉ${C.reset} dans ${C.bold}${rel}${C.reset}`);
    console.error(`       → ${link.target} ${C.dim}(fichier introuvable)${C.reset}`);
  }
}

/* ── Point d'entrée ────────────────────────────────────────────── */
function main() {
  console.log(`\n${C.bold}╔══════════════════════════════════════════════════╗${C.reset}`);
  console.log(`${C.bold}║  validate-links.mjs — Liens internes du site    ║${C.reset}`);
  console.log(`${C.bold}╚══════════════════════════════════════════════════╝${C.reset}`);

  /* Récupérer tous les fichiers HTML à la racine */
  const htmlFiles = fs.readdirSync(ROOT)
    .filter(f => f.endsWith('.html'))
    .map(f => path.join(ROOT, f))
    .sort();

  console.log(`\n${C.info}  ${htmlFiles.length} page(s) HTML détectée(s)\n`);

  for (const file of htmlFiles) {
    const rel  = path.relative(ROOT, file);
    const html = fs.readFileSync(file, 'utf8');
    const links = extractInternalLinks(html, file);

    console.log(`${C.bold}── ${rel}${C.reset} ${C.dim}(${links.length} lien(s) interne(s))${C.reset}`);

    if (links.length === 0) {
      counts.skipped++;
      console.log(`  ${C.info}  ${C.dim}Aucun lien interne trouvé${C.reset}`);
      continue;
    }

    for (const link of links) {
      checkLink(file, link);
    }
  }

  /* ── Rapport final ─────────────────────────────────────────── */
  console.log(`\n${C.bold}── Résumé ──────────────────────────────────────${C.reset}`);
  console.log(`  ${C.ok}  OK     : ${counts.ok}`);
  if (counts.broken > 0) {
    console.error(`  ${C.err}  Cassés : ${counts.broken}`);
    console.log(`\n${C.bold}Résultat : ÉCHEC${C.reset} — ${counts.broken} lien(s) cassé(s) à corriger.\n`);
    process.exit(1);
  } else {
    console.log(`\n${C.bold}Résultat : ${C.ok} SUCCÈS${C.reset} — tous les liens internes sont valides.\n`);
    process.exit(0);
  }
}

main();
