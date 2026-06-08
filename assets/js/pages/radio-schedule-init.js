/* assets/js/pages/radio-schedule-init.js
   Rendu dynamique du programme radio depuis radio-schedule.json.
   Dépendances : utils.js (chargé avant ce fichier) */
(function () {
  'use strict';

  var esc = (window.EduRoyaume && window.EduRoyaume.escapeHtml)
    ? window.EduRoyaume.escapeHtml
    : function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };

  fetch('assets/data/radio-schedule.json')
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (data) {
      var grid = document.getElementById('program-grid');
      if (!grid) return;
      grid.innerHTML = data.map(function (p) {
        var tz = p.timezone ? ' <span class="program-tz">(' + esc(p.timezone) + ')</span>' : '';
        return '<div class="program-card">'
          + '<div class="program-time">' + esc(p.time) + tz + '</div>'
          + '<div class="program-name">' + esc(p.name) + '</div>'
          + '<div class="program-desc">' + esc(p.desc) + '</div>'
        + '</div>';
      }).join('');
    })
    .catch(function (e) {
      var grid = document.getElementById('program-grid');
      if (grid) grid.innerHTML = '<p style="padding:1rem;color:rgba(255,255,255,.5)">Programme temporairement indisponible.</p>';
      console.error('radio-schedule.json load error:', e);
    });
})();
