/* ============================================================
   assets/js/media-player.js — Lecteur audio partagé
   Utilisé par : audios.html, podcasts.html

   Dépendances :
     - assets/js/utils.js  (EduRoyaume.escapeHtml, EduRoyaume.formatDuration)

   Usage :
     EduRoyaume.MediaPlayer.init({
       dataUrl      : 'assets/data/audios.json',   // URL du JSON
       containerId  : 'audio-sections-container',   // id du conteneur
       icon         : '#icon-headphones',            // SVG use href
       labelSingular: 'partie',
       labelPlural  : 'parties',
     });
   ============================================================ */

(function (global) {
  'use strict';

  var esc = function(s) {
    return (global.EduRoyaume && global.EduRoyaume.escapeHtml)
      ? global.EduRoyaume.escapeHtml(s)
      : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  };

  var fmt = function(s) {
    return (global.EduRoyaume && global.EduRoyaume.formatDuration)
      ? global.EduRoyaume.formatDuration(s)
      : ((!s || isNaN(s)) ? '0:00' : Math.floor(s/60) + ':' + String(Math.floor(s%60)).padStart(2,'0'));
  };

  /* ── DOM refs ─────────────────────────────────────────── */
  var audio, playerBar, pbTitle, pbSeries, btnPP, ppIcon;
  var btnPrev, btnNext, pbBarWrap, pbBarFill;
  var pbCurrent, pbDuration, volSlider, btnMute, btnClose, pbStatus;

  /* ── État ─────────────────────────────────────────────── */
  var allRows    = [];
  var currentIdx = -1;
  var stallRetryId    = null;
  var saveThrottleId  = null;
  var pendingResumeTime = 0;
  var dataKey = '';   /* clé localStorage dérivée de opts.dataUrl */

  /* ── Persistance localStorage ─────────────────────────── */
  function lsKey(suffix) { return 'er_mp_' + dataKey + '_' + suffix; }

  function saveState() {
    try {
      localStorage.setItem(lsKey('idx'),  String(currentIdx));
      localStorage.setItem(lsKey('time'), String(Math.floor(audio.currentTime)));
    } catch(e) { /* quota dépassé ou mode privé — silencieux */ }
  }

  function saveVolume() {
    try { localStorage.setItem('er_mp_volume', String(audio.volume)); } catch(e) {}
  }

  function clearSavedState() {
    try {
      localStorage.removeItem(lsKey('idx'));
      localStorage.removeItem(lsKey('time'));
    } catch(e) {}
  }

  function restoreVolume() {
    try {
      var v = parseFloat(localStorage.getItem('er_mp_volume'));
      if (!isNaN(v) && v >= 0 && v <= 1) {
        audio.volume      = v;
        volSlider.value   = v;
      }
    } catch(e) {}
  }

  /* Afficher la bannière "Reprendre depuis X:XX" si état sauvegardé */
  function showResumeBanner(container) {
    try {
      var idx  = parseInt(localStorage.getItem(lsKey('idx')),  10);
      var time = parseInt(localStorage.getItem(lsKey('time')), 10);
      if (isNaN(idx) || idx < 0 || isNaN(time) || time <= 10) return;
      if (idx >= allRows.length) { clearSavedState(); return; }

      var row   = allRows[idx];
      var title = row.dataset.title || (row.querySelector('.ar-title') || {}).textContent || '—';
      var mins  = Math.floor(time / 60);
      var secs  = String(time % 60).padStart(2, '0');
      var label = mins + ':' + secs;

      var banner = document.createElement('div');
      banner.className = 'mp-resume-banner';
      banner.setAttribute('role', 'alert');
      banner.innerHTML =
        '<span>▶ Reprendre <strong>' + esc(title) + '</strong> depuis ' + esc(label) + '</span>' +
        '<button class="mp-resume-yes" aria-label="Reprendre la lecture">Reprendre</button>' +
        '<button class="mp-resume-no"  aria-label="Ignorer">✕</button>';

      banner.querySelector('.mp-resume-yes').addEventListener('click', function() {
        pendingResumeTime = time;
        loadTrack(idx);
        banner.remove();
      });
      banner.querySelector('.mp-resume-no').addEventListener('click', function() {
        clearSavedState();
        banner.remove();
      });

      container.insertBefore(banner, container.firstChild);
    } catch(e) {}
  }

  /* ── Markup d'une ligne audio (partagé listing + page Nouveau) ── */
  function rowHtml(t, num) {
    return '<div class="audio-row"' +
      ' data-src="'    + esc(t.src)    + '"' +
      ' data-title="'  + esc(t.title)  + '"' +
      ' data-series="' + esc(t.series) + '">' +
      '<button class="ar-play-btn" aria-label="Lire">' +
        '<svg width="14" height="14"><use href="#icon-play"/></svg>' +
      '</button>' +
      '<div>' +
        '<span class="ar-num">' + String(num).padStart(2, '0') + '</span>' +
        '<span class="ar-playing-bars"><span></span><span></span><span></span><span></span></span>' +
      '</div>' +
      '<div class="ar-info">' +
        '<div class="ar-title">' + esc(t.title)  + '</div>' +
        '<span class="ar-series">' + esc(t.series) + '</span>' +
      '</div>' +
      '<span class="ar-dur">' + (t.duration ? esc(t.duration) : '—') + '</span>' +
      '<a href="' + esc(t.src) + '" target="_blank" rel="noopener noreferrer"' +
        ' class="ar-dl" aria-label="Télécharger">' +
        '<svg width="15" height="15"><use href="#icon-download"/></svg>' +
      '</a>' +
    '</div>';
  }

  /* ── Rendu des sections depuis les données JSON ───────── */
  function renderAudioSections(tracks, opts) {
    var order  = [];
    var groups = {};
    for (var i = 0; i < tracks.length; i++) {
      var t = tracks[i];
      var key = t.sectionName;
      if (!groups[key]) { groups[key] = []; order.push(key); }
      groups[key].push(t);
    }

    var html = order.map(function(name) {
      var rows  = groups[name];
      var count = rows.length;
      var label = count > 1 ? opts.labelPlural : opts.labelSingular;

      var cards = rows.map(function(t, i) { return rowHtml(t, i + 1); }).join('');

      return '<section class="audio-section">' +
        '<div class="audio-section-hd">' +
          '<div class="audio-hd-icon">' +
            '<svg width="14" height="14"><use href="' + opts.icon + '"/></svg>' +
          '</div>' +
          '<span class="audio-hd-name">'  + esc(name)  + '</span>' +
          '<span class="audio-hd-count">' + count + ' ' + label + '</span>' +
        '</div>' +
        '<div class="audio-list">' + cards + '</div>' +
      '</section>';
    }).join('');

    document.getElementById(opts.containerId).innerHTML = html;
  }

  /* ── Durée — mise à jour depuis la piste active ──────── */
  /* Appelée quand loadedmetadata se déclenche sur la piste en cours.
     Les durées initiales viennent du JSON (plus de new Audio() au chargement). */
  function setRowDuration(row, seconds) {
    if (!row || !seconds || isNaN(seconds)) return;
    var durEl = row.querySelector('.ar-dur');
    if (durEl) durEl.textContent = fmt(seconds);
  }

  /* ── État de lecture ──────────────────────────────────── */
  function setPlayingRow(idx) {
    allRows.forEach(function(r, i) {
      r.classList.toggle('playing', i === idx);
      var btn = r.querySelector('.ar-play-btn use');
      if (btn) btn.setAttribute('href', (i === idx && !audio.paused) ? '#icon-pause' : '#icon-play');
    });
  }

  function setStatus(type, html) {
    if (!pbStatus) return;
    pbStatus.className = 'pb-status' + (type ? ' is-' + type : '');
    pbStatus.innerHTML = html || '';
  }
  function clearStatus() { setStatus('', ''); }

  function showAudioError() {
    var dl = (currentIdx >= 0 && currentIdx < allRows.length)
      ? allRows[currentIdx].querySelector('.ar-dl') : null;
    var dlHtml = dl
      ? ' — <a href="' + dl.href + '" target="_blank" rel="noopener noreferrer">Télécharger</a>'
      : '';
    setStatus('error', '⚠️ Fichier indisponible' + dlHtml);
    setPlayingRow(-1);
  }

  /* ── Chargement de piste ──────────────────────────────── */
  function loadTrack(idx) {
    if (idx < 0 || idx >= allRows.length) return;
    clearStatus();
    clearTimeout(stallRetryId);
    clearTimeout(saveThrottleId);
    saveThrottleId = null;
    /* Effacer le flag d'erreur sur toutes les lignes */
    allRows.forEach(function(r) { r.classList.remove('is-error'); });
    currentIdx = idx;
    var row    = allRows[idx];
    var src    = row.dataset.src || '';
    if (!src) return;
    var title  = row.dataset.title  || (row.querySelector('.ar-title') || {}).textContent || '—';
    var series = row.dataset.series || '—';

    pbTitle.textContent  = title;
    pbSeries.textContent = series;
    playerBar.classList.add('visible');
    setPlayingRow(idx);

    audio.src = src;
    audio.load();
    setStatus('loading', 'Chargement…');
    audio.play()
      .then(function() { clearStatus(); })
      .catch(function(err) {
        if (err.name === 'NotAllowedError') { clearStatus(); }
        else { showAudioError(); }
      });
  }

  function togglePlay() {
    if (audio.paused) audio.play(); else audio.pause();
  }

  /* ── Initialisation des rows (appeler après renderAudioSections) */
  function initRows() {
    allRows = Array.from(document.querySelectorAll('.audio-row'));
    allRows.forEach(function(row, idx) {
      var btn = row.querySelector('.ar-play-btn');
      if (btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          if (idx === currentIdx) { togglePlay(); return; }
          loadTrack(idx);
        });
      }
      row.addEventListener('click', function(e) {
        if (e.target.closest('.ar-dl') || e.target.closest('.ar-play-btn')) return;
        if (idx === currentIdx) { togglePlay(); return; }
        loadTrack(idx);
      });
    });
  }

  /* ── Contrôles player ─────────────────────────────────── */
  function bindPlayerControls() {
    btnPP.addEventListener('click', function() {
      if (currentIdx === -1 && allRows.length) { loadTrack(0); return; }
      togglePlay();
    });
    btnNext.addEventListener('click', function() {
      loadTrack((currentIdx + 1) % allRows.length);
    });
    btnPrev.addEventListener('click', function() {
      if (audio.currentTime > 3) { audio.currentTime = 0; return; }
      loadTrack((currentIdx - 1 + allRows.length) % allRows.length);
    });

    audio.addEventListener('play', function() {
      clearStatus();
      ppIcon.setAttribute('href', '#icon-pause');
      setPlayingRow(currentIdx);
      var btn = allRows[currentIdx] && allRows[currentIdx].querySelector('.ar-play-btn use');
      if (btn) btn.setAttribute('href', '#icon-pause');
    });
    audio.addEventListener('pause', function() {
      ppIcon.setAttribute('href', '#icon-play');
      var btn = allRows[currentIdx] && allRows[currentIdx].querySelector('.ar-play-btn use');
      if (btn) btn.setAttribute('href', '#icon-play');
    });
    audio.addEventListener('ended', function() {
      clearStatus();
      loadTrack((currentIdx + 1) % allRows.length);
    });
    audio.addEventListener('error', function() {
      /* Marquer la ligne en erreur pour feedback visuel par piste */
      if (currentIdx >= 0 && allRows[currentIdx]) {
        allRows[currentIdx].classList.add('is-error');
      }
      showAudioError();
    });
    audio.addEventListener('stalled', function() {
      clearTimeout(stallRetryId);
      /* Afficher message avec bouton "Réessayer" manuel */
      var retryHtml = '⚠️ Connexion instable — ' +
        '<button class="pb-retry-btn" aria-label="Réessayer la lecture">Réessayer</button>';
      setStatus('loading', retryHtml);
      if (pbStatus) {
        var retryBtn = pbStatus.querySelector('.pb-retry-btn');
        if (retryBtn) retryBtn.addEventListener('click', function() {
          clearTimeout(stallRetryId);
          var src = audio.src; var t = audio.currentTime;
          audio.src = src; audio.load();
          audio.currentTime = t;
          audio.play().catch(function() { showAudioError(); });
        });
      }
      /* Auto-retry après 10s si toujours en stall */
      stallRetryId = setTimeout(function() {
        if (!audio.paused) {
          var src = audio.src; var t = audio.currentTime;
          audio.src = src; audio.load();
          audio.currentTime = t;
          audio.play().catch(function() { showAudioError(); });
        }
      }, 10000);
    });
    audio.addEventListener('canplay',  function() { clearTimeout(stallRetryId); clearStatus(); });
    audio.addEventListener('waiting',  function() { setStatus('loading', 'Mise en mémoire tampon…'); });
    audio.addEventListener('loadedmetadata', function() {
      pbDuration.textContent = fmt(audio.duration);
      setRowDuration(allRows[currentIdx], audio.duration);
      /* Reprendre depuis la position sauvegardée si demandé */
      if (pendingResumeTime > 0) {
        audio.currentTime = pendingResumeTime;
        pendingResumeTime = 0;
      }
    });
    audio.addEventListener('timeupdate', function() {
      if (!audio.duration) return;
      var pct = (audio.currentTime / audio.duration) * 100;
      pbBarFill.style.width    = pct + '%';
      pbCurrent.textContent    = fmt(audio.currentTime);
      pbDuration.textContent   = fmt(audio.duration);
      setRowDuration(allRows[currentIdx], audio.duration);
      /* Sauvegarder position en localStorage (throttlé, toutes les 10s) */
      if (!saveThrottleId) {
        saveThrottleId = setTimeout(function() { saveThrottleId = null; saveState(); }, 10000);
      }
    });

    pbBarWrap.addEventListener('click', function(e) {
      if (!audio.duration) return;
      var rect = pbBarWrap.getBoundingClientRect();
      audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
    });

    volSlider.addEventListener('input', function() {
      audio.volume = volSlider.value;
      saveVolume();
    });
    btnMute.addEventListener('click', function() {
      audio.muted = !audio.muted;
      volSlider.value = audio.muted ? 0 : audio.volume;
    });

    btnClose.addEventListener('click', function() {
      clearTimeout(stallRetryId);
      clearTimeout(saveThrottleId);
      saveThrottleId = null;
      clearSavedState();
      clearStatus();
      audio.pause(); audio.src = '';
      playerBar.classList.remove('visible');
      allRows.forEach(function(r) {
        r.classList.remove('playing', 'is-error');
        var btn = r.querySelector('.ar-play-btn use');
        if (btn) btn.setAttribute('href', '#icon-play');
      });
      currentIdx = -1;
    });
  }

  /* ── Point d'entrée public ────────────────────────────── */
  /**
   * @param {object} opts
   * @param {string} opts.dataUrl        URL du fichier JSON
   * @param {string} opts.containerId    id du conteneur HTML (défaut: 'audio-sections-container')
   * @param {string} opts.icon           SVG use href (défaut: '#icon-headphones')
   * @param {string} opts.labelSingular  (défaut: 'partie')
   * @param {string} opts.labelPlural    (défaut: 'parties')
   */
  function init(opts) {
    opts = Object.assign({
      dataUrl       : 'assets/data/audios.json',
      containerId   : 'audio-sections-container',
      icon          : '#icon-headphones',
      labelSingular : 'partie',
      labelPlural   : 'parties',
    }, opts || {});

    setupDom();

    /* Icône de la barre alignée sur celle de la page (casque, micro…) */
    var pbIconUse = playerBar ? playerBar.querySelector('.pb-icon use') : null;
    if (pbIconUse) pbIconUse.setAttribute('href', opts.icon);

    /* Clé localStorage dérivée de l'URL du fichier de données */
    dataKey = opts.dataUrl.replace(/[^a-z0-9]/gi, '_').replace(/_+/g, '_').slice(-30);

    /* Charger les données */
    fetch(opts.dataUrl)
      .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function(tracks) {
        var container = document.getElementById(opts.containerId);
        renderAudioSections(tracks, opts);
        initRows();
        /* Proposer de reprendre depuis l'état sauvegardé */
        if (container) showResumeBanner(container);
        if (typeof opts.onLoaded === 'function') opts.onLoaded(tracks);
      })
      .catch(function(e) {
        var container = document.getElementById(opts.containerId);
        if (container) {
          container.innerHTML =
            '<p style="padding:2rem;color:rgba(255,255,255,.5)">' +
            'Impossible de charger les audios. Veuillez réessayer.</p>';
        }
        console.error(opts.dataUrl + ' load error:', e);
      });
  }

  /* ── Barre player — source unique du markup ───────────── */
  /* Injectée dans <body> si absente. Les pages n'ont plus à
     copier ce bloc dans leur HTML. */
  var PLAYER_BAR_HTML =
    '<div class="player-bar" id="playerBar" role="region" aria-label="Lecteur audio">' +
      '<audio id="audioEl" preload="none"></audio>' +
      '<div class="pb-track">' +
        '<div class="pb-icon"><svg width="22" height="22"><use href="#icon-headphones"/></svg></div>' +
        '<div class="pb-info">' +
          '<div class="pb-title" id="pbTitle">—</div>' +
          '<div class="pb-series" id="pbSeries">—</div>' +
          '<div class="pb-status" id="pbStatus" role="alert" aria-live="polite"></div>' +
        '</div>' +
      '</div>' +
      '<div class="pb-controls">' +
        '<div class="pb-btns">' +
          '<button class="pb-btn pb-skip" id="btnPrev" aria-label="Précédent"><svg width="20" height="20"><use href="#icon-skip-prev"/></svg></button>' +
          '<button class="pb-btn-main" id="btnPlayPause" aria-label="Lecture / Pause"><svg width="18" height="18" id="ppIcon"><use href="#icon-play"/></svg></button>' +
          '<button class="pb-btn pb-skip" id="btnNext" aria-label="Suivant"><svg width="20" height="20"><use href="#icon-skip-next"/></svg></button>' +
        '</div>' +
        '<div class="pb-progress">' +
          '<span class="pb-time" id="pbCurrent">0:00</span>' +
          '<div class="pb-bar-wrap" id="pbBarWrap"><div class="pb-bar-fill" id="pbBarFill"></div></div>' +
          '<span class="pb-time" id="pbDuration">0:00</span>' +
        '</div>' +
      '</div>' +
      '<div class="pb-vol">' +
        '<button class="pb-vol-btn" id="btnMute" aria-label="Muet"><svg width="16" height="16"><use href="#icon-volume"/></svg></button>' +
        '<input type="range" class="pb-vol-slider" id="volSlider" min="0" max="1" step="0.02" value="1" aria-label="Volume">' +
      '</div>' +
      '<button class="pb-close" id="btnClose" aria-label="Fermer le lecteur">' +
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">' +
          '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>' +
        '</svg>' +
      '</button>' +
    '</div>';

  function ensurePlayerBar() {
    if (!document.getElementById('playerBar')) {
      document.body.insertAdjacentHTML('beforeend', PLAYER_BAR_HTML);
    }
  }

  /* ── Refs DOM + contrôles (commun init / attach) ──────── */
  function setupDom() {
    ensurePlayerBar();

    audio      = document.getElementById('audioEl');
    playerBar  = document.getElementById('playerBar');
    pbTitle    = document.getElementById('pbTitle');
    pbSeries   = document.getElementById('pbSeries');
    btnPP      = document.getElementById('btnPlayPause');
    ppIcon     = document.getElementById('ppIcon');
    btnPrev    = document.getElementById('btnPrev');
    btnNext    = document.getElementById('btnNext');
    pbBarWrap  = document.getElementById('pbBarWrap');
    pbBarFill  = document.getElementById('pbBarFill');
    pbCurrent  = document.getElementById('pbCurrent');
    pbDuration = document.getElementById('pbDuration');
    volSlider  = document.getElementById('volSlider');
    btnMute    = document.getElementById('btnMute');
    btnClose   = document.getElementById('btnClose');
    pbStatus   = document.getElementById('pbStatus');

    bindPlayerControls();
    restoreVolume();
  }

  /* ── attach(storageKey) — pages dont les .audio-row sont déjà
     rendues dans le DOM (ex. nouveau.html). Ne charge aucun JSON,
     ne rend rien : branche la barre + les lignes existantes. ───── */
  function attach(storageKey) {
    setupDom();
    dataKey = String(storageKey || document.body.getAttribute('data-page') || 'page')
      .replace(/[^a-z0-9]/gi, '_').slice(-30);
    initRows();
  }

  /* ── Export ───────────────────────────────────────────── */
  global.EduRoyaume             = global.EduRoyaume || {};
  global.EduRoyaume.MediaPlayer = { init: init, attach: attach, rowHtml: rowHtml };

})(window);
