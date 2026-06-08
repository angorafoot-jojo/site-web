/* assets/js/pages/partners-init.js
   Rendu dynamique des partenaires depuis partners.json.
   Dépendances : utils.js (chargé avant ce fichier) */
(function () {
  'use strict';

  var esc = (window.EduRoyaume && window.EduRoyaume.escapeHtml)
    ? window.EduRoyaume.escapeHtml
    : function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };

  fetch('assets/data/partners.json')
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (data) {
      var grid = document.getElementById('partners-grid');
      if (!grid) return;
      grid.innerHTML = data.map(function (p) {
        return '<div class="partner-card">'
          + '<div class="partner-icon" style="background:linear-gradient(135deg,' + esc(p.color_start) + ',' + esc(p.color_end) + ')">' + esc(p.initial) + '</div>'
          + '<div>'
            + '<div class="partner-type">' + esc(p.type) + '</div>'
            + '<h2 class="partner-name">' + esc(p.name) + '</h2>'
          + '</div>'
          + '<a href="' + esc(p.url) + '" target="_blank" rel="noopener noreferrer" class="partner-link">'
            + esc(p.label)
            + ' <svg width="14" height="14" aria-hidden="true"><use href="#icon-external"/></svg>'
          + '</a>'
        + '</div>';
      }).join('');
    })
    .catch(function (e) {
      var grid = document.getElementById('partners-grid');
      if (grid) grid.innerHTML = '<p style="padding:2rem;text-align:center;color:rgba(28,28,40,.45)">Impossible de charger les partenaires.</p>';
      console.error('partners.json load error:', e);
    });
})();
