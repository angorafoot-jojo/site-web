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
        'YouTube <svg width="11" height="11"><use href="#icon-arrow-right"/></svg></a>';

      var cards = items.map(function(v) {
        var ytId  = esc(v.youtube_id);
        var title = esc(v.title);
        var meta  = esc(v.meta || '');
        var thumb = 'https://img.youtube.com/vi/' + ytId + '/mqdefault.jpg';
        var href  = 'https://youtu.be/' + ytId;
        /* onerror : si la miniature YouTube est indisponible, afficher le placeholder SVG */
        var imgFallback = 'this.onerror=null;this.src=\'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22320%22 height=%22180%22 viewBox=%220 0 320 180%22%3E%3Crect width=%22320%22 height=%22180%22 fill=%22%23e8e0d0%22/%3E%3Ctext x=%22160%22 y=%2295%22 font-family=%22sans-serif%22 font-size=%2214%22 fill=%22%23999%22 text-anchor=%22middle%22%3EImage non disponible%3C/text%3E%3C/svg%3E\'';
        return '<a href="' + href + '" target="_blank" rel="noopener noreferrer" class="vc">' +
          '<div class="vc-img">' +
            '<img src="' + esc(thumb) + '" alt="Miniature — ' + title + '" loading="lazy" onerror="' + imgFallback + '">' +
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

  /* ── Message "aucun résultat" ─────────────────────────── */
  function renderEmpty(query) {
    var container = document.getElementById('video-sections-container');
    if (!container) return;
    container.innerHTML =
      '<p style="padding:2rem;text-align:center;color:var(--warm-grey)">' +
      'Aucun résultat pour « ' + esc(query) + ' »</p>';
  }

  /* ── Chargement depuis JSON + init recherche ──────────── */
  var _allVideos = [];

  fetch('assets/data/videos.json')
    .then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    })
    .then(function(videos) {
      _allVideos = videos;
      renderVideoSections(videos);

      /* Activer la recherche si le module EduRoyaume.Search est chargé */
      if (global.EduRoyaume && global.EduRoyaume.Search) {
        global.EduRoyaume.Search.init({
          inputId  : 'video-search',
          countId  : 'video-count',
          getData  : function () { return _allVideos; },
          getTerms : function (v) {
            return (v.title || '') + ' ' + (v.series || '') + ' ' + (v.meta || '');
          },
          renderFn : function (items, query) {
            if (items.length === 0 && query) { renderEmpty(query); }
            else { renderVideoSections(items); }
          },
        });
      }
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
