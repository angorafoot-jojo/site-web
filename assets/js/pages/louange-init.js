/* assets/js/pages/louange-init.js
   Rendu dynamique des cantiques depuis louange.json.
   Dépendances : utils.js (chargé avant ce fichier) */
(function () {
  'use strict';

  var esc = (window.EduRoyaume && window.EduRoyaume.escapeHtml)
    ? window.EduRoyaume.escapeHtml
    : function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };

  function cardHtml(c) {
    var isYt     = c.type === 'yt';
    var titleS   = esc(c.title);
    var sourceS  = esc(c.source);
    var thumb    = isYt
      ? '<img src="https://img.youtube.com/vi/' + sourceS + '/mqdefault.jpg" alt="' + titleS + '" loading="lazy">'
      : '<div class="cantique-thumb-audio"><svg width="52" height="52"><use href="#icon-cantique"/></svg></div>';
    var badge    = isYt ? 'YouTube' : 'Vidéo';
    var dataType = isYt ? 'yt' : 'drive';

    /* <button> = élément sémantique nativement cliquable + focusable au clavier
       (CLAUDE.md §4 : interdit les <div role="button">) */
    return '<button class="cantique-card"'
      + ' type="button"'
      + ' data-type="' + dataType + '"'
      + ' data-id="'   + sourceS  + '"'
      + ' data-title="' + titleS  + '"'
      + ' aria-label="Lire — ' + titleS + '">'
      + '<div class="cantique-thumb">'
        + thumb
        + '<span class="cantique-type-badge badge-yt">' + badge + '</span>'
        + '<div class="cantique-play-overlay"><div class="cantique-play-btn" aria-hidden="true">'
          + '<svg width="20" height="20"><use href="#icon-play"/></svg>'
        + '</div></div>'
      + '</div>'
      + '<div class="cantique-body">'
        + '<div class="cantique-title">' + titleS + '</div>'
        + '<div class="cantique-meta"><svg width="12" height="12" aria-hidden="true"><use href="#icon-cantique"/></svg> Cantique</div>'
      + '</div>'
    + '</button>';
  }

  fetch('assets/data/louange.json')
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (data) {
      var grid = document.getElementById('cantique-grid');
      if (grid) grid.innerHTML = data.map(cardHtml).join('');
    })
    .catch(function (e) {
      var grid = document.getElementById('cantique-grid');
      if (grid) grid.innerHTML = '<p style="padding:2rem;text-align:center;color:rgba(255,255,255,.5)">Impossible de charger les cantiques.</p>';
      console.error('louange.json load error:', e);
    });
})();
