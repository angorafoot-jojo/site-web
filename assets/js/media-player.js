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
  var stallRetryId = null;

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

      var cards = rows.map(function(t, i) {
        return '<div class="audio-row"' +
          ' data-src="'    + esc(t.src)    + '"' +
          ' data-title="'  + esc(t.title)  + '"' +
          ' data-series="' + esc(t.series) + '">' +
          '<button class="ar-play-btn" aria-label="Lire">' +
            '<svg width="14" height="14"><use href="#icon-play"/></svg>' +
          '</button>' +
          '<div>' +
            '<span class="ar-num">' + String(i + 1).padStart(2, '0') + '</span>' +
            '<span class="ar-playing-bars"><span></span><span></span><span></span><span></span></span>' +
          '</div>' +
          '<div class="ar-info">' +
            '<div class="ar-title">' + esc(t.title)  + '</div>' +
            '<span class="ar-series">' + esc(t.series) + '</span>' +
          '</div>' +
          '<span class="ar-dur">—</span>' +
          '<a href="' + esc(t.src) + '" target="_blank" rel="noopener noreferrer"' +
            ' class="ar-dl" aria-label="Télécharger">' +
            '<svg width="15" height="15"><use href="#icon-download"/></svg>' +
          '</a>' +
        '</div>';
      }).join('');

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

  /* ── Durées ───────────────────────────────────────────── */
  function setRowDuration(row, seconds) {
    if (!row || !seconds || isNaN(seconds)) return;
    var durEl = row.querySelector('.ar-dur');
    if (durEl) durEl.textContent = fmt(seconds);
  }

  function probeDuration(row) {
    return new Promise(function(resolve) {
      var src = (row && row.dataset && row.dataset.src) || '';
      if (!src) return resolve();
      var durEl = row.querySelector('.ar-dur');
      if (durEl && durEl.textContent !== '—') return resolve();
      var probe    = new Audio();
      var settled  = false;
      var cleanup  = function() { probe.removeAttribute('src'); probe.load(); };
      var finish   = function(seconds) {
        if (settled) return;
        settled = true;
        if (seconds && !isNaN(seconds)) setRowDuration(row, seconds);
        cleanup();
        resolve();
      };
      probe.preload = 'metadata';
      probe.addEventListener('loadedmetadata', function() { finish(probe.duration); }, { once: true });
      probe.addEventListener('error',          function() { finish(null);           }, { once: true });
      probe.src = src;
    });
  }

  async function preloadDurations() {
    for (var i = 0; i < allRows.length; i++) {
      await probeDuration(allRows[i]);
    }
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
    audio.addEventListener('error', function() { showAudioError(); });
    audio.addEventListener('stalled', function() {
      setStatus('loading', '⚠️ Connexion instable — nouvelle tentative dans 8s…');
      clearTimeout(stallRetryId);
      stallRetryId = setTimeout(function() {
        if (!audio.paused) {
          var src = audio.src;
          audio.load(); audio.src = src;
          audio.play().catch(function() { showAudioError(); });
        }
      }, 8000);
    });
    audio.addEventListener('canplay',  function() { clearTimeout(stallRetryId); clearStatus(); });
    audio.addEventListener('waiting',  function() { setStatus('loading', 'Mise en mémoire tampon…'); });
    audio.addEventListener('timeupdate', function() {
      if (!audio.duration) return;
      var pct = (audio.currentTime / audio.duration) * 100;
      pbBarFill.style.width    = pct + '%';
      pbCurrent.textContent    = fmt(audio.currentTime);
      pbDuration.textContent   = fmt(audio.duration);
      setRowDuration(allRows[currentIdx], audio.duration);
    });
    audio.addEventListener('loadedmetadata', function() {
      pbDuration.textContent = fmt(audio.duration);
      setRowDuration(allRows[currentIdx], audio.duration);
    });

    pbBarWrap.addEventListener('click', function(e) {
      if (!audio.duration) return;
      var rect = pbBarWrap.getBoundingClientRect();
      audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
    });

    volSlider.addEventListener('input', function() { audio.volume = volSlider.value; });
    btnMute.addEventListener('click', function() {
      audio.muted = !audio.muted;
      volSlider.value = audio.muted ? 0 : audio.volume;
    });

    btnClose.addEventListener('click', function() {
      clearTimeout(stallRetryId);
      clearStatus();
      audio.pause(); audio.src = '';
      playerBar.classList.remove('visible');
      allRows.forEach(function(r) {
        r.classList.remove('playing');
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

    /* Récupérer les refs DOM */
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

    /* Charger les données */
    fetch(opts.dataUrl)
      .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function(tracks) {
        renderAudioSections(tracks, opts);
        initRows();
        preloadDurations();
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

  /* ── Export ───────────────────────────────────────────── */
  global.EduRoyaume             = global.EduRoyaume || {};
  global.EduRoyaume.MediaPlayer = { init: init };

})(window);
