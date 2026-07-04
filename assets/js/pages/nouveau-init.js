/* assets/js/pages/nouveau-init.js
   Page « Nouveau » (nouveau.html) — vue d'ensemble des derniers contenus.
   Chaque section se remplit depuis les JSON de assets/data/ et lance
   le contenu DIRECTEMENT (pas de page intermédiaire) :
     1. Dernière vidéo ajoutée        → videos.json   → lien YouTube
     2. Derniers messages audio (×3)  → audios.json   → lecture dans la barre player
     3. Dernières séries podcast (×3) → podcasts.json → lecture dans la barre player
     4. Louange mise en avant         → louange.json  → lien YouTube
     5. Article mis en avant          → articles.json → ouvre le lecteur EPUB (#lire-<id>)
   Les sections sont indépendantes : si un JSON échoue, les autres s'affichent.
   Dépendances : utils.js, media-player.js (chargés avant ce fichier) */

(function () {
  'use strict';

  var esc = (window.EduRoyaume && window.EduRoyaume.escapeHtml)
    ? window.EduRoyaume.escapeHtml
    : function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };

  function loadJson(file) {
    return fetch('assets/data/' + file)
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); });
  }

  /* Ouvre un lien vers YouTube dans un nouvel onglet */
  function ytLink(link, videoId) {
    link.href   = 'https://youtu.be/' + encodeURIComponent(videoId);
    link.target = '_blank';
    link.rel    = 'noopener noreferrer';
  }

  /* ── 1. Dernière vidéo ajoutée → YouTube ────────────────────── */
  (function () {
    var thumb = document.getElementById('nv-video-thumb');
    var meta  = document.getElementById('nv-video-meta');
    var title = document.getElementById('nv-video-title');
    var link  = document.getElementById('nv-video-link');
    if (!title) return;

    loadJson('videos.json').then(function (videos) {
      var v = videos[videos.length - 1];
      if (!v || !v.title || !v.youtube_id) return;
      if (thumb) { thumb.src = 'https://img.youtube.com/vi/' + encodeURIComponent(v.youtube_id) + '/mqdefault.jpg'; thumb.alt = v.title; }
      if (meta)  meta.innerHTML = '<span>' + esc(v.series || 'Vidéo') + '</span><span>' + esc(v.meta || 'Dernier ajout') + '</span>';
      title.textContent = v.title;
      if (link) ytLink(link, v.youtube_id);
    }).catch(function (e) { console.error('[Nouveau] videos.json :', e); });
  })();

  /* ── 2 & 3. Audios + podcasts → lignes jouables (barre player) ── */
  function fillRows(gridId, file, listHref, listLabel) {
    var grid = document.getElementById(gridId);
    if (!grid) return Promise.resolve();
    return loadJson(file).then(function (tracks) {
      grid.innerHTML = '<div class="audio-list">' +
        tracks.slice(0, 3)
          .filter(function (t) { return t.title && t.src; })
          .map(function (t, i) { return EduRoyaume.MediaPlayer.rowHtml(t, i + 1); })
          .join('') +
        '</div>';
    }).catch(function (e) {
      console.error('[Nouveau] ' + file + ' :', e);
      grid.innerHTML = '<p>Impossible de charger cette section — ' +
        '<a href="' + esc(listHref) + '">' + esc(listLabel) + '</a></p>';
    });
  }

  Promise.all([
    fillRows('nv-audios',   'audios.json',   'audios.html',   'voir tous les messages audio'),
    fillRows('nv-podcasts', 'podcasts.json', 'podcasts.html', 'voir toutes les séries podcast')
  ]).then(function () {
    /* Brancher la barre player sur les lignes rendues (une seule fois) */
    if (document.querySelector('.audio-row')) EduRoyaume.MediaPlayer.attach('nouveau');
  });

  /* ── 4. Louange mise en avant → YouTube ─────────────────────── */
  (function () {
    var thumb = document.getElementById('nv-louange-thumb');
    var title = document.getElementById('nv-louange-title');
    var link  = document.getElementById('nv-louange-link');
    if (!title) return;
    loadJson('louange.json').then(function (cantiques) {
      var c = cantiques[0];
      if (!c || !c.title) return;
      title.textContent = c.title;
      if (c.type === 'yt' && c.source) {
        if (thumb) { thumb.src = 'https://img.youtube.com/vi/' + encodeURIComponent(c.source) + '/mqdefault.jpg'; thumb.alt = c.title; }
        if (link) { ytLink(link, c.source); link.innerHTML = 'Écouter sur YouTube <svg width="14" height="14"><use href="#icon-arrow-right"/></svg>'; }
      }
    }).catch(function (e) { console.error('[Nouveau] louange.json :', e); });
  })();

  /* ── 5. Article mis en avant → lecteur EPUB direct ──────────── */
  (function () {
    var meta  = document.getElementById('nv-article-meta');
    var title = document.getElementById('nv-article-title');
    var link  = document.getElementById('nv-article-link');
    if (!title) return;
    loadJson('articles.json').then(function (articles) {
      /* Même règle que la page d'accueil : featured d'abord, sinon le plus récent */
      var fr = articles.filter(function (a) { return !a.en; });
      var a = fr.filter(function (x) { return x.featured; })[0]
        || fr.sort(function (x, y) { return y.year - x.year || y.id - x.id; })[0];
      if (!a || !a.title) return;
      if (meta) meta.innerHTML = '<span>' + esc(String(a.year || '')) + '</span><span>Article mis en avant</span>';
      title.textContent = a.title;
      /* #lire-<id> : articles.html ouvre le lecteur EPUB directement (book-catalogue.js) */
      if (link) link.href = 'articles.html#lire-' + encodeURIComponent(a.id);
    }).catch(function (e) { console.error('[Nouveau] articles.json :', e); });
  })();

})();
