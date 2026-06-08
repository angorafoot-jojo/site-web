#!/usr/bin/env node
/* scripts/fetch-durations.mjs
   Récupère les durées audio via ffprobe et met à jour
   assets/data/audios.json et assets/data/podcasts.json.

   Usage :
     node scripts/fetch-durations.mjs              → tous les fichiers
     node scripts/fetch-durations.mjs audios       → audios.json seulement
     node scripts/fetch-durations.mjs podcasts     → podcasts.json seulement
     node scripts/fetch-durations.mjs --dry-run    → affiche sans écrire

   Prérequis : ffprobe (brew install ffmpeg)
*/

import { execFile }   from 'child_process';
import { promisify }  from 'util';
import { readFile, writeFile } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const execFileAsync = promisify(execFile);
const __dir  = dirname(fileURLToPath(import.meta.url));
const ROOT   = join(__dir, '..');
const ARGS   = process.argv.slice(2);
const DRY    = ARGS.includes('--dry-run');
const FILTER = ARGS.find(a => a !== '--dry-run') || 'all';

const FILES = {
  audios:   'assets/data/audios.json',
  podcasts: 'assets/data/podcasts.json',
};

/* ── Formater les secondes en MM:SS ou HH:MM:SS ── */
function formatDuration(seconds) {
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  }
  return `${m}:${String(sec).padStart(2, '0')}`;
}

/* ── Récupérer la durée via ffprobe ── */
async function getDuration(url) {
  try {
    const { stdout } = await execFileAsync('ffprobe', [
      '-v', 'error',
      '-show_entries', 'format=duration',
      '-of', 'default=noprint_wrappers=1:nokey=1',
      url,
    ], { timeout: 30000 });
    const seconds = parseFloat(stdout.trim());
    if (isNaN(seconds)) return null;
    return formatDuration(seconds);
  } catch {
    return null;
  }
}

/* ── Traiter un fichier JSON ── */
async function processFile(name, path) {
  const fullPath = join(ROOT, path);
  const raw = await readFile(fullPath, 'utf8');
  const tracks = JSON.parse(raw);

  const todo = tracks.filter(t => !t.duration);
  console.log(`\n── ${name} (${path})`);
  console.log(`   ${tracks.length} pistes — ${todo.length} sans durée`);

  if (todo.length === 0) {
    console.log('   ✓ Toutes les durées sont déjà présentes.');
    return;
  }

  let updated = 0;
  let failed  = 0;

  for (let i = 0; i < todo.length; i++) {
    const t = todo[i];
    process.stdout.write(`   [${i + 1}/${todo.length}] ${t.title.slice(0, 50).padEnd(52)}… `);
    const dur = await getDuration(t.src);
    if (dur) {
      // Met à jour l'objet dans le tableau original
      const idx = tracks.findIndex(x => x.id === t.id);
      tracks[idx].duration = dur;
      process.stdout.write(`${dur}\n`);
      updated++;
    } else {
      process.stdout.write('ÉCHEC\n');
      failed++;
    }
  }

  console.log(`\n   Résultat : ${updated} mis à jour, ${failed} échecs`);

  if (DRY) {
    console.log('   [--dry-run] Fichier NON écrit.');
    return;
  }

  await writeFile(fullPath, JSON.stringify(tracks, null, 2) + '\n', 'utf8');
  console.log(`   ✓ ${path} mis à jour.`);
}

/* ── Point d'entrée ── */
(async () => {
  console.log('╔══════════════════════════════════════════════════╗');
  console.log('║  fetch-durations.mjs — L\'Évangile du Royaume    ║');
  console.log(`║  Mode : ${DRY ? '--dry-run (lecture seule)        ' : 'écriture JSON                      '}║`);
  console.log('╚══════════════════════════════════════════════════╝');

  const targets = FILTER === 'all'
    ? Object.entries(FILES)
    : Object.entries(FILES).filter(([k]) => k === FILTER);

  if (targets.length === 0) {
    console.error(`Fichier inconnu : "${FILTER}". Options : audios, podcasts, all`);
    process.exit(1);
  }

  for (const [name, path] of targets) {
    await processFile(name, path);
  }

  console.log('\n✓ Terminé.');
})();
