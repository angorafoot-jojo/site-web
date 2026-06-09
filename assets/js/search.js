/* ============================================================
   assets/js/search.js — Module de recherche/filtrage côté client
   Utilisé par : videos.html (et extensible à d'autres pages)

   Dépendances : aucune (standalone)

   Usage :
     EduRoyaume.Search.init({
       inputId    : 'video-search',  // ID de l'input
       countId    : 'video-count',   // ID du compteur (optionnel)
       getData    : function() { return allItems; },
       renderFn   : function(items, query) { /* met à jour le DOM */ },
       getTerms   : function(item) { return item.title + ' ' + item.series; },
       debounceMs : 180,             // délai debounce (défaut)
     });

   La fonction renderFn reçoit :
     - items  : tableau filtré (tous les items si query est vide)
     - query  : la chaîne de recherche normalisée (lowercase, trimmed)
   ============================================================ */

(function (global) {
  'use strict';

  /**
   * init — attache la logique de filtrage à un champ de recherche.
   * @param {Object} opts — configuration (voir Usage ci-dessus)
   */
  function init(opts) {
    opts = Object.assign({
      inputId    : '',
      countId    : null,
      getData    : function () { return []; },
      renderFn   : function () {},
      getTerms   : function (item) { return item.title || ''; },
      debounceMs : 180,
    }, opts || {});

    var input = document.getElementById(opts.inputId);
    if (!input) {
      console.warn('EduRoyaume.Search: input introuvable :', opts.inputId);
      return;
    }

    var countEl = opts.countId ? document.getElementById(opts.countId) : null;
    var timer;

    function doFilter() {
      var q       = input.value.trim().toLowerCase();
      var all     = opts.getData();
      var results = q
        ? all.filter(function (item) {
            return opts.getTerms(item).toLowerCase().indexOf(q) !== -1;
          })
        : all;

      /* Compteur de résultats */
      if (countEl) {
        if (q) {
          countEl.textContent = results.length + ' résultat' + (results.length !== 1 ? 's' : '');
          countEl.style.display = '';
        } else {
          countEl.style.display = 'none';
        }
      }

      opts.renderFn(results, q);
    }

    /* Debounce sur input + déclenchement immédiat sur clear (type="search") */
    input.addEventListener('input', function () {
      clearTimeout(timer);
      timer = setTimeout(doFilter, opts.debounceMs);
    });
    input.addEventListener('search', function () {
      clearTimeout(timer);
      doFilter();
    });
  }

  /* ── Export ─────────────────────────────────────────────────── */
  global.EduRoyaume        = global.EduRoyaume || {};
  global.EduRoyaume.Search = { init: init };

})(window);
