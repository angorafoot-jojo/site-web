/* ============================================================
   assets/js/epub-reader.js — Lecteur EPUB partagé
   Utilisé par : livres.html, articles.html

   Lazy-charge JSZip + epub.js au premier appel.

   Usage :
     EduRoyaume.EpubReader.open({ id, title, epub, pdf });
   ============================================================ */

(function (global) {
  'use strict';

  /* ── CDN (SRI non requis : les URLs incluent la version fixée) ── */
  var JSZIP_URL  = 'https://cdn.jsdelivr.net/npm/jszip@3.10.1/dist/jszip.min.js';
  var EPUBJS_URL = 'https://cdn.jsdelivr.net/npm/epubjs@0.3.93/dist/epub.min.js';

  /* ── Chargement dynamique de script ────────────────────── */
  function loadScript(url) {
    return new Promise(function(resolve, reject) {
      if (document.querySelector('script[src="' + url + '"]')) return resolve();
      var s = document.createElement('script');
      s.src = url;
      s.onload  = resolve;
      s.onerror = function() { reject(new Error('Failed to load ' + url)); };
      document.head.appendChild(s);
    });
  }

  var epubJsLoaded = false;

  async function ensureEpubJs() {
    if (epubJsLoaded || global.ePub) { epubJsLoaded = true; return; }
    await loadScript(JSZIP_URL);
    await loadScript(EPUBJS_URL);
    epubJsLoaded = true;
  }

  /* ── Refs DOM (résolues à l'init) ──────────────────────── */
  var overlay, readerTitle, pageInfo, progressFill, epubViewerEl;
  var readerBody, pageLoading, readerError, errorLink;
  var arrowPrev, arrowNext, btnPageMode, btnScrollMode;
  var btnClose, btnBack, btnErrClose, btnZoomIn, btnZoomOut, zoomLevel, btnReaderDl;

  /* ── État ─────────────────────────────────────────────── */
  var epubBook      = null;
  var rendition     = null;
  var currentMode   = 'page';
  var fontSizePct   = 100;
  var currentBookId = null;
  var isLoading     = false;
  var lastFocused   = null;
  var bound         = false;

  /* ── Sauvegarde / restauration de position ─────────────── */
  function savePos(id, cfi) {
    try { localStorage.setItem('epub_pos_' + id, cfi); } catch(e) {}
  }
  function getPos(id) {
    try { return localStorage.getItem('epub_pos_' + id); } catch(e) { return null; }
  }

  /* ── Thème lisible ──────────────────────────────────────── */
  function applyEpubTheme() {
    if (!rendition) return;
    rendition.themes.register('site', {
      'body'      : { 'font-family': 'Georgia,"Times New Roman",serif', 'line-height': '1.75',
                      'padding': '1.5rem 2.5rem', 'color': '#1C1C28', 'background': '#FFFDF7' },
      'p'         : { 'margin-bottom': '.85em', 'text-align': 'justify' },
      'h1,h2,h3'  : { 'color': '#07122a', 'margin-top': '1.4em', 'line-height': '1.3' },
      'img'       : { 'max-width': '100%', 'height': 'auto' }
    });
    rendition.themes.select('site');
    rendition.themes.fontSize(fontSizePct + '%');
  }

  /* ── Progress bar + flèches ─────────────────────────────── */
  function handleRelocated(location) {
    pageLoading.style.display = 'none';
    if (location.start && location.start.percentage !== undefined) {
      var pct = Math.round(location.start.percentage * 100);
      pageInfo.textContent     = pct + '%';
      progressFill.style.width = pct + '%';
      if (currentBookId && location.start.cfi) savePos(currentBookId, location.start.cfi);
    }
    arrowPrev.classList.toggle('disabled', !!location.atStart);
    arrowNext.classList.toggle('disabled', !!location.atEnd);
  }

  /* ── Nettoyage ──────────────────────────────────────────── */
  function destroyReader() {
    if (rendition) { try { rendition.destroy(); } catch(e){} rendition = null; }
    if (epubBook)  { try { epubBook.destroy();  } catch(e){} epubBook  = null; }
    epubViewerEl.innerHTML = '';
  }

  /* ── Fermer le lecteur ──────────────────────────────────── */
  function closeReader() {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
    readerError.classList.remove('visible');
    destroyReader();
    if (lastFocused && lastFocused.focus) lastFocused.focus();
  }

  /* ── Changement de mode lecture ─────────────────────────── */
  async function switchMode(newMode) {
    if (currentMode === newMode || !currentBookId || isLoading) return;
    var cfi = null;
    if (rendition) {
      try {
        var loc = rendition.currentLocation();
        if (loc && loc.start) cfi = loc.start.cfi;
      } catch(e) {}
    }
    var prevMode = currentMode;
    currentMode  = newMode;
    try {
      await openItem({ id: currentBookId, _resume: cfi });
    } catch(e) {
      currentMode = prevMode;
      btnPageMode.classList.toggle('active',   prevMode === 'page');
      btnScrollMode.classList.toggle('active', prevMode === 'scroll');
    }
  }

  /* ── Zoom ───────────────────────────────────────────────── */
  function applyZoom() {
    if (rendition) rendition.themes.fontSize(fontSizePct + '%');
    if (zoomLevel) zoomLevel.textContent = fontSizePct + '%';
  }

  /* ── Ouverture principale ───────────────────────────────── */
  async function openItem(item) {
    if (isLoading) return;

    var restoreCfi = item._resume || null;
    /* Premier appel : résoudre DOM + lier événements */
    if (!bound) bindEvents();

    /* Lazy-load epub.js si pas encore chargé */
    try {
      await ensureEpubJs();
    } catch(err) {
      console.error('epub-reader: impossible de charger epub.js', err);
      return;
    }

    isLoading     = true;
    currentBookId = item.id;
    lastFocused   = document.activeElement;
    fontSizePct   = 100;

    destroyReader();

    overlay.classList.add('open');
    document.body.style.overflow = 'hidden';

    /* Reset UI */
    readerTitle.textContent   = item.title || '';
    pageInfo.textContent      = '—';
    progressFill.style.width  = '0%';
    pageLoading.style.display = 'flex';
    readerError.classList.remove('visible');
    if (errorLink) errorLink.href = item.pdf || '#';
    if (zoomLevel) zoomLevel.textContent = '100%';

    if (item.pdf) { btnReaderDl.href = item.pdf; btnReaderDl.classList.remove('hidden'); }
    else          { btnReaderDl.classList.add('hidden'); }

    /* Mode scroll automatique sur mobile */
    if (window.innerWidth < 900) currentMode = 'scroll';

    btnPageMode.classList.toggle('active',   currentMode === 'page');
    btnScrollMode.classList.toggle('active', currentMode === 'scroll');
    readerBody.classList.toggle('scroll-mode', currentMode === 'scroll');

    setTimeout(function() { if (btnBack) btnBack.focus(); }, 80);

    try {
      epubBook  = ePub(item.epub);  /* global ePub fourni par epub.js */
      var flowMode = currentMode === 'page' ? 'paginated' : 'scrolled-continuous';
      rendition = epubBook.renderTo('epub-viewer', {
        flow: flowMode, width: '100%', height: '100%', spread: 'none'
      });

      /* Swipe dans les iframes */
      rendition.hooks.content.register(function(contents) {
        var doc = contents.document;
        if (!doc) return;
        var tx = 0;
        doc.addEventListener('touchstart', function(e) {
          tx = e.changedTouches[0].clientX;
        }, { passive: true });
        doc.addEventListener('touchend', function(e) {
          var dx = e.changedTouches[0].clientX - tx;
          if (Math.abs(dx) > 50 && rendition && currentMode === 'page') {
            dx < 0 ? rendition.next().catch(function(){}) : rendition.prev().catch(function(){});
          }
        });
      });

      rendition.on('relocated', handleRelocated);

      var cfi = restoreCfi || getPos(item.id) || undefined;

      await Promise.race([
        rendition.display(cfi),
        new Promise(function(_, rej) { setTimeout(function() { rej(new Error('timeout')); }, 15000); })
      ]);

      applyEpubTheme();
      pageLoading.style.display = 'none';

    } catch(err) {
      console.warn('EPUB load error:', err.message || err);
      pageLoading.style.display = 'none';
      readerError.classList.add('visible');
    } finally {
      isLoading = false;
    }
  }

  /* ── Liaison des événements (une seule fois) ────────────── */
  function bindEvents() {
    overlay      = document.getElementById('reader-overlay');
    readerTitle  = document.getElementById('reader-book-title');
    pageInfo     = document.getElementById('reader-page-info');
    progressFill = document.getElementById('reader-progress-fill');
    epubViewerEl = document.getElementById('epub-viewer');
    readerBody   = document.querySelector('.reader-body');
    pageLoading  = document.getElementById('page-loading');
    readerError  = document.getElementById('reader-error');
    errorLink    = document.getElementById('error-open-link');   /* optionnel */
    arrowPrev    = document.getElementById('arrow-prev');
    arrowNext    = document.getElementById('arrow-next');
    btnPageMode  = document.getElementById('btn-page-mode');
    btnScrollMode= document.getElementById('btn-scroll-mode');
    btnClose     = document.getElementById('btn-reader-close');
    btnBack      = document.getElementById('btn-reader-back');
    btnErrClose  = document.getElementById('btn-error-close');
    btnZoomIn    = document.getElementById('btn-zoom-in');
    btnZoomOut   = document.getElementById('btn-zoom-out');
    zoomLevel    = document.getElementById('reader-zoom-level');
    btnReaderDl  = document.getElementById('btn-reader-dl');

    /* Mode initial */
    currentMode = window.innerWidth < 900 ? 'scroll' : 'page';

    /* Fermer */
    btnClose.addEventListener('click',    closeReader);
    btnBack.addEventListener('click',     closeReader);
    btnErrClose.addEventListener('click', closeReader);

    /* Navigation */
    arrowPrev.addEventListener('click', function() { if (rendition) rendition.prev().catch(function(){}); });
    arrowNext.addEventListener('click', function() { if (rendition) rendition.next().catch(function(){}); });

    /* Mode lecture */
    btnPageMode.addEventListener('click',   function() { switchMode('page');   });
    btnScrollMode.addEventListener('click', function() { switchMode('scroll'); });

    /* Zoom */
    btnZoomIn.addEventListener('click', function() {
      if (fontSizePct >= 200) return;
      fontSizePct += 15; applyZoom();
    });
    btnZoomOut.addEventListener('click', function() {
      if (fontSizePct <= 70) return;
      fontSizePct -= 15; applyZoom();
    });

    /* Clavier */
    document.addEventListener('keydown', function(e) {
      if (!overlay.classList.contains('open')) return;
      if (e.key === 'Escape') { closeReader(); return; }
      if (!rendition || currentMode !== 'page') return;
      if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   { e.preventDefault(); rendition.prev().catch(function(){}); }
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); rendition.next().catch(function(){}); }
    });

    /* Focus trap */
    overlay.addEventListener('keydown', function(e) {
      if (e.key !== 'Tab') return;
      var focusable = Array.from(overlay.querySelectorAll(
        'button:not([disabled]), a[href], select, input, [tabindex]:not([tabindex="-1"])'
      ));
      if (!focusable.length) return;
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
      }
    });

    /* Swipe sur le conteneur (fallback) */
    var touchStartX = 0;
    epubViewerEl.addEventListener('touchstart', function(e) {
      touchStartX = e.changedTouches[0].clientX;
    }, { passive: true });
    epubViewerEl.addEventListener('touchend', function(e) {
      var dx = e.changedTouches[0].clientX - touchStartX;
      if (Math.abs(dx) > 50 && rendition && currentMode === 'page') {
        dx < 0 ? rendition.next().catch(function(){}) : rendition.prev().catch(function(){});
      }
    });

    /* Resize avec debounce */
    var resizeTimer;
    window.addEventListener('resize', function() {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function() { if (rendition) rendition.resize('100%', '100%'); }, 100);
    });

    bound = true;
  }

  /* ── Export ─────────────────────────────────────────────── */
  global.EduRoyaume            = global.EduRoyaume || {};
  global.EduRoyaume.EpubReader = { open: openItem };

})(window);
