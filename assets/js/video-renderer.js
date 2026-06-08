/* ============================================================
   assets/js/video-renderer.js — Rendu dynamique des vidéos
   Utilisé par : videos.html

   Dépendances :
     - assets/js/utils.js  (EduRoyaume.escapeHtml)

   Charge assets/data/videos.json et génère le HTML des
   sections de vidéos dans #video-sections-container.
   ============================================================ */

(function (global) {
  'use strict';

  var esc = function(s) {
    return (global.EduRoyaume && global.EduRoyaume.escapeHtml)
      ? global.EduRoyaume.escapeHtml(s)
      : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  };

  var YT_CHANNEL = 'https://www.youtube.com/channel/UCycAoa7k7LqyvG_TQWlG5_g';

  /* ── Rendu des sections vidéo ─────────────────────────── */
  function renderVideoSections(videos) {
    /* Regrouper par série en conservant l'ordre d'apparition */
    var order  = [];
    var groups = {};
    for (var i = 0; i < videos.length; i++) {
      var v = videos[i];
      var s = v.series || 'Messages individuels';
      if (!groups[s]) { groups[s] = []; order.push(s); }
      groups[s].push(v);
    }

    var html = order.map(function(name) {
      var items        = groups[name];
      var count        = items.length;
      var isIndividual = (name === 'Messages individuels');

      var link = isIndividual ? '' :
        '<a href="' + YT_CHANNEL + '" target="_blank" rel="noopener noreferrer" class="series-hd-link">' +
        'YouTube <svg width="11" height="11"><use href="#icon-arrow-r"/></svg></a>';

      var cards = items.map(function(v) {
        var ytId  = esc(v.youtube_id);
        var title = esc(v.title);
        var meta  = esc(v.meta || '');
        var thumb = 'https://img.youtube.com/vi/' + ytId + '/mqdefault.jpg';
        var href  = 'https://youtu.be/' + ytId;
        return '<a href="' + href + '" target="_blank" rel="noopener noreferrer" class="vc">' +
          '<div class="vc-img">' +
            '<img src="' + esc(thumb) + '" alt="" loading="lazy">' +
            '<div class="vc-overlay"><div class="vc-play">' +
              '<svg width="18" height="18"><use href="#icon-play"/></svg>' +
            '</div></div>' +
          '</div>' +
          '<div class="vc-body">' +
            '<div class="vc-title">' + title + '</div>' +
            '<div class="vc-meta">'  + meta  + '</div>' +
          '</div>' +
        '</a>';
      }).join('');

      return '<section class="series-section">' +
        '<div class="series-hd">' +
          '<div class="series-hd-icon"><svg width="14" height="14"><use href="#icon-film"/></svg></div>' +
          '<span class="series-hd-name">'  + esc(name) + '</span>' +
          '<span class="series-hd-count">' + count + ' vidéo' + (count > 1 ? 's' : '') + '</span>' +
          link +
        '</div>' +
        '<div class="series-grid">' + cards + '</div>' +
      '</section>';
    }).join('');

    var container = document.getElementById('video-sections-container');
    if (container) container.innerHTML = html;
  }

  /* ── Chargement depuis JSON ───────────────────────────── */
  fetch('assets/data/videos.json')
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(videos) {
      renderVideoSections(videos);
    })
    .catch(function(e) {
      var container = document.getElementById('video-sections-container');
      if (container) {
        container.innerHTML =
          '<p style="padding:2rem;text-align:center;color:var(--warm-grey)">' +
          'Impossible de charger les vidéos. Veuillez réessayer.' +
          '</p>';
      }
      console.error('videos.json load error:', e);
    });

})(window);
