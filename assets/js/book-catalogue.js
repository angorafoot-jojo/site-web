/* ============================================================
   assets/js/book-catalogue.js — Catalogue partagé livres & articles
   Utilisé par : livres.html, articles.html

   Dépendances :
     - assets/js/utils.js  (EduRoyaume.escapeHtml)

   Usage :
     EduRoyaume.BookCatalogue.init({
       dataUrl   : 'assets/data/books.json',
       gridId    : 'book-grid',
       countId   : 'lib-results-count',
       searchId  : 'lib-search',
       sortId    : 'select-sort',
       dispoId   : 'select-dispo',
       langId    : 'select-lang',      // livres seulement (null pour articles)
       catId     : 'select-cat',       // articles seulement (null pour livres)
       singular  : 'livre',
       plural    : 'livres',
       openFn    : openBook,           // function(id) — ouvre le lecteur
       availFn   : function(item) { return !!(item.epub || item.pdf); },
       isEnFn    : function(item) { return item.tags.includes('en'); },
       errorMsg  : 'Impossible de charger les données.',
     });
   ============================================================ */

(function (global) {
  'use strict';

  var esc = function(s) {
    return (global.EduRoyaume && global.EduRoyaume.escapeHtml)
      ? global.EduRoyaume.escapeHtml(s)
      : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  };

  /* ── Estimation de l'année de publication ─────────────────── */
  function getYear(item) {
    if (item.year) return item.year;
    /* Extraire depuis une URL PDF datée : .../2023/... */
    if (item.pdf && item.pdf.startsWith('http')) {
      var m = item.pdf.match(/\/(\d{4})\//);
      if (m) return parseInt(m[1]);
    }
    /* Estimation basée sur l'id pour les livres sans URL datée */
    if (item.id >= 1700) return 2022;
    if (item.id >= 1500) return 2021;
    if (item.id >= 1000) return 2020;
    return 2019;
  }

  /* ── HTML d'une carte ──────────────────────────────────────── */
  function cardHtml(item, opts) {
    var avail     = opts.availFn(item);
    var isEn      = opts.isEnFn(item);
    var titleSafe = esc(item.title);
    var id        = item.id;

    /* Pas d'inline events (onclick/onkeydown interdit CLAUDE.md §4).
       La délégation d'événements est attachée une fois sur le grid dans init(). */
    return '<div class="book-card ' + (avail ? '' : 'unavailable') + '"' +
      ' role="listitem"' +
      (avail ? ' tabindex="0"' : '') +
      ' data-id="' + id + '">' +

      '<div class="book-cover gc-' + (item.color || 'blue') + '">' +
        '<div class="book-cover-deco" aria-hidden="true"></div>' +
        (isEn ? '<span class="book-cover-badge badge-en">EN</span>' : '') +
        (!avail
          ? '<span class="book-cover-badge badge-soon">Bientôt</span>'
          : '<span class="book-cover-badge badge-pdf">EPUB</span>') +
        '<span class="book-cover-title">' + titleSafe + '</span>' +
      '</div>' +

      '<div class="book-meta">' +
        '<p class="book-title">' + titleSafe + '</p>' +
        '<button class="book-read-btn ' + (avail ? 'available' : 'unavailable-btn') + '"' +
          (avail ? '' : ' disabled') +
          ' aria-label="' + titleSafe + (avail ? ' — Lire maintenant' : ' — Bientôt disponible') + '">' +
          (avail
            ? '<svg width="14" height="14"><use href="#icon-book-open"/></svg> Lire maintenant'
            : '<svg width="14" height="14"><use href="#icon-book-open"/></svg> Bientôt disponible') +
        '</button>' +
        (item.pdf
          ? '<a class="book-dl-btn" href="' + esc(item.pdf) + '" target="_blank" rel="noopener noreferrer"' +
            ' title="Télécharger le PDF — ' + titleSafe + '">' +
            '<svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24" aria-hidden="true">' +
              '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
              '<polyline points="7 10 12 15 17 10"/>' +
              '<line x1="12" y1="15" x2="12" y2="3"/>' +
            '</svg>' +
            ' Télécharger PDF' +
          '</a>'
          : '') +
      '</div>' +
    '</div>';
  }

  /* ── Registre interne : gridId → DATA (pour find()) ──────────── */
  var _stores = {};

  /* ── Point d'entrée public ─────────────────────────────────── */
  function init(opts) {
    opts = Object.assign({
      dataUrl    : '',
      gridId     : 'book-grid',
      countId    : 'lib-results-count',
      searchId   : 'lib-search',
      sortId     : 'select-sort',
      dispoId    : 'select-dispo',
      langId     : null,
      catId      : null,
      singular   : 'élément',
      plural     : 'éléments',
      openFn     : null,
      openFnName : 'openBook',
      availFn    : function(item) { return !!(item.epub || item.pdf); },
      isEnFn     : function(item) { return !!(item.tags && item.tags.includes('en')); },
      errorMsg   : 'Impossible de charger les données.',
    }, opts || {});

    /* Résoudre openFnName depuis openFn si fourni */
    if (opts.openFn && !opts.openFnName) {
      opts.openFnName = opts.openFn.name || 'openBook';
    }

    /* Récupérer les éléments DOM */
    var grid     = document.getElementById(opts.gridId);
    var search   = document.getElementById(opts.searchId);
    var selSort  = document.getElementById(opts.sortId);
    var selDispo = document.getElementById(opts.dispoId);
    var selLang  = opts.langId  ? document.getElementById(opts.langId)  : null;
    var selCat   = opts.catId   ? document.getElementById(opts.catId)   : null;
    var count    = document.getElementById(opts.countId);

    var DATA = [];
    var debounce;

    function renderGrid() {
      var query = search.value.trim().toLowerCase();
      var sort  = selSort  ? selSort.value  : 'date-desc';
      var dispo = selDispo ? selDispo.value : 'all';
      var lang  = selLang  ? selLang.value  : 'all';
      var cat   = selCat   ? selCat.value   : 'all';

      var list = DATA.filter(function(item) {
        /* Recherche titre */
        if (query && !item.title.toLowerCase().includes(query)) return false;
        /* Filtre disponibilité — accepte 'epub', 'pdf' comme "disponible" */
        if (dispo !== 'all' && dispo !== 'soon') {
          if (!opts.availFn(item)) return false;
        }
        if (dispo === 'soon' && opts.availFn(item)) return false;
        /* Filtre langue (livres) */
        if (lang === 'en' && !opts.isEnFn(item)) return false;
        if (lang === 'fr' &&  opts.isEnFn(item)) return false;
        /* Filtre catégorie (articles) */
        if (cat !== 'all' && item.cat !== cat) return false;
        return true;
      });

      /* Tri */
      list = list.slice().sort(function(a, b) {
        switch (sort) {
          case 'date-desc':  return getYear(b) - getYear(a) || b.id - a.id;
          case 'date-asc':   return getYear(a) - getYear(b) || a.id - b.id;
          case 'title-asc':  return a.title.localeCompare(b.title, 'fr');
          case 'title-desc': return b.title.localeCompare(a.title, 'fr');
          default: return 0;
        }
      });

      /* Compteur */
      count.textContent = list.length === 1
        ? '1 ' + opts.singular
        : list.length + ' ' + opts.plural;

      /* Rendu */
      if (list.length === 0) {
        grid.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:rgba(28,28,40,.45);padding:3rem 0">' +
          'Aucun résultat pour « ' + esc(search.value) + ' »</p>';
        return;
      }

      grid.innerHTML = list.map(function(item) {
        return cardHtml(item, opts);
      }).join('');
    }

    /* Événements */
    search.addEventListener('input', function() {
      clearTimeout(debounce);
      debounce = setTimeout(renderGrid, 180);
    });
    if (selSort)  selSort.addEventListener('change',  renderGrid);
    if (selDispo) selDispo.addEventListener('change', renderGrid);
    if (selLang)  selLang.addEventListener('change',  renderGrid);
    if (selCat)   selCat.addEventListener('change',   renderGrid);

    /* Délégation d'événements sur le grid — ouvre le lecteur au clic sur une carte.
       Attachée une seule fois ici ; les cartes sont recréées à chaque renderGrid(). */
    grid.addEventListener('click', function(e) {
      /* Laisser passer les clics sur le lien de téléchargement PDF */
      if (e.target.closest('.book-dl-btn')) return;
      var card = e.target.closest('.book-card[data-id]');
      if (!card || card.classList.contains('unavailable')) return;
      var id = parseInt(card.dataset.id, 10);
      if (isNaN(id)) return;
      if (typeof opts.openFn === 'function') {
        opts.openFn(id);
      } else if (opts.openFnName && typeof window[opts.openFnName] === 'function') {
        window[opts.openFnName](id);
      }
    });
    /* Navigation clavier : Enter/Space sur une carte disponible = clic */
    grid.addEventListener('keydown', function(e) {
      if (e.key !== 'Enter' && e.key !== ' ') return;
      var card = e.target.closest('.book-card[data-id]');
      if (!card || card.classList.contains('unavailable')) return;
      e.preventDefault();
      card.click();
    });

    /* Chargement JSON */
    fetch(opts.dataUrl)
      .then(function(r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function(data) {
        DATA = data;
        _stores[opts.gridId] = DATA; /* registre pour find() */
        count.textContent = DATA.length + ' ' + opts.plural;
        renderGrid();
      })
      .catch(function(e) {
        grid.innerHTML = '<p style="grid-column:1/-1;text-align:center;color:rgba(28,28,40,.45);padding:3rem 0">' +
          esc(opts.errorMsg) + '</p>';
        console.error(opts.dataUrl + ' load error:', e);
      });
  }

  /* ── find(gridId, id) — retrouver un item pour le lecteur ─────── */
  function find(gridId, id) {
    var data = _stores[gridId] || [];
    for (var i = 0; i < data.length; i++) {
      if (data[i].id === id) return data[i];
    }
    return null;
  }

  /* ── Export ─────────────────────────────────────────────────── */
  global.EduRoyaume                 = global.EduRoyaume || {};
  global.EduRoyaume.BookCatalogue   = { init: init, find: find };

})(window);
