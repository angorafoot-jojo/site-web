/* ============================================================
   assets/js/radio-player.js — Lecteur radio en direct
   Utilisé par : radio.html

   Dépendances : aucune (standalone)
   ============================================================ */

(function () {
  'use strict';

  /* ── Configuration ──────────────────────────────────────────── */
  var NOWPLAYING_API  = 'https://parole-prophetique-fm.levangileduroyaume.com/api/nowplaying/1';
  var FETCH_TIMEOUT   = 8000;   /* ms — abandon si l'API ne répond pas */
  var POLL_IDLE       = 15000;  /* ms — polling quand l'onglet est visible mais pas en lecture */
  var POLL_PLAYING    = 10000;  /* ms — polling pendant la lecture active */
  var STALL_TIMEOUT   = 8000;   /* ms — délai avant de signaler une connexion instable */

  /* ── DOM ────────────────────────────────────────────────────── */
  var audio      = document.getElementById('radio-main-audio');
  var playBtn    = document.getElementById('radio-main-play');
  var pathEl     = document.getElementById('radio-main-path');
  var labelEl    = document.getElementById('radio-play-label-text');
  var statusEl   = document.getElementById('radio-status');
  var volEl      = document.getElementById('radio-main-vol');
  var npTitle    = document.getElementById('nowplaying-title');
  var npArtist   = document.getElementById('nowplaying-artist');
  var npProgress = document.getElementById('nowplaying-progress');

  var PLAY_D  = 'M8 5v14l11-7z';
  var PAUSE_D = 'M6 19h4V5H6v14zm8-14v14h4V5h-4z';

  var pollTimer   = null;
  var stallTimer  = null;
  var isPlaying   = false;

  /* ── Volume persistant ──────────────────────────────────────── */
  var savedVol = parseFloat(localStorage.getItem('radio_volume'));
  if (!isNaN(savedVol) && savedVol >= 0 && savedVol <= 1) {
    audio.volume = savedVol;
    if (volEl) volEl.value = savedVol;
  }

  /* ── NowPlaying API (avec timeout AbortController) ──────────── */
  function fetchNowPlaying() {
    /* Stoppe silencieusement si l'onglet est en arrière-plan */
    if (document.hidden) return;

    var controller = new AbortController();
    var timeoutId  = setTimeout(function() { controller.abort(); }, FETCH_TIMEOUT);

    fetch(NOWPLAYING_API, { signal: controller.signal })
      .then(function(r) {
        clearTimeout(timeoutId);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function(data) {
        if (!data || !data.now_playing) return;
        var np = data.now_playing;
        if (npTitle)   npTitle.textContent  = np.song && np.song.title  ? np.song.title  : (np.title  || 'Parole Prophétique FM');
        if (npArtist)  npArtist.textContent = np.song && np.song.artist ? np.song.artist : (np.artist || '');
        if (npProgress && np.duration > 0) {
          var pct = Math.min(100, Math.round((np.elapsed / np.duration) * 100));
          npProgress.style.width = pct + '%';
        }
      })
      .catch(function(err) {
        clearTimeout(timeoutId);
        /* AbortError = timeout silencieux, pas d'affichage d'erreur UI */
        if (err.name !== 'AbortError' && npTitle) {
          npTitle.textContent = 'Parole Prophétique FM';
        }
      });
  }

  /* ── Gestion du polling (s'arrête si onglet caché) ─────────── */
  function startPolling(interval) {
    stopPolling();
    fetchNowPlaying();
    pollTimer = setInterval(fetchNowPlaying, interval);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  /* Page Visibility API : pause le polling si l'onglet est masqué */
  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      stopPolling();
    } else {
      startPolling(isPlaying ? POLL_PLAYING : POLL_IDLE);
    }
  });

  /* Démarrage initial */
  startPolling(POLL_IDLE);

  /* ── États du player ────────────────────────────────────────── */
  function setState(state) {
    clearTimeout(stallTimer);

    if (state === 'playing') {
      isPlaying = true;
      pathEl.setAttribute('d', PAUSE_D);
      playBtn.setAttribute('aria-label', 'Mettre en pause');
      playBtn.setAttribute('aria-pressed', 'true');
      playBtn.classList.add('is-playing');
      labelEl.textContent  = 'En cours de diffusion';
      statusEl.textContent = '';
      statusEl.className   = 'radio-status';
      startPolling(POLL_PLAYING);

    } else if (state === 'loading') {
      pathEl.setAttribute('d', PAUSE_D);
      playBtn.setAttribute('aria-pressed', 'true');
      labelEl.textContent  = 'Connexion en cours…';
      statusEl.textContent = 'Chargement du flux…';
      statusEl.className   = 'radio-status is-loading';

    } else if (state === 'stalled') {
      statusEl.textContent = '⚠️ Connexion instable — nouvelle tentative…';
      statusEl.className   = 'radio-status is-loading';
      /* Retry automatique après STALL_TIMEOUT */
      stallTimer = setTimeout(function() {
        if (!audio.paused) {
          audio.load();
          audio.play().catch(function() { setState('error'); });
        }
      }, STALL_TIMEOUT);

    } else if (state === 'error') {
      isPlaying = false;
      pathEl.setAttribute('d', PLAY_D);
      playBtn.setAttribute('aria-pressed', 'false');
      playBtn.classList.remove('is-playing');
      labelEl.textContent  = 'Appuyez pour écouter';
      statusEl.innerHTML   = '⚠️ Flux indisponible — <a href="' + NOWPLAYING_API.replace('/api/nowplaying/1', '') + '" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline">ouvrir le lecteur web</a>';
      statusEl.className   = 'radio-status is-error';
      startPolling(POLL_IDLE);

    } else { /* paused / idle */
      isPlaying = false;
      pathEl.setAttribute('d', PLAY_D);
      playBtn.setAttribute('aria-label', 'Lancer la radio en direct');
      playBtn.setAttribute('aria-pressed', 'false');
      playBtn.classList.remove('is-playing');
      labelEl.textContent  = 'Appuyez pour écouter';
      statusEl.textContent = '';
      statusEl.className   = 'radio-status';
      startPolling(POLL_IDLE);
    }
  }

  /* ── Contrôles ──────────────────────────────────────────────── */
  playBtn.addEventListener('click', function() {
    if (audio.paused) {
      setState('loading');
      audio.load();
      audio.play().catch(function(err) {
        /* NotAllowedError = autoplay bloqué par le navigateur (pas une erreur stream) */
        if (err.name === 'NotAllowedError') {
          setState('idle');
          statusEl.textContent = 'Cliquez à nouveau pour démarrer la radio.';
          statusEl.className   = 'radio-status';
        } else {
          setState('error');
        }
      });
    } else {
      audio.pause();
      setState('paused');
    }
  });

  audio.addEventListener('playing', function() { setState('playing'); });
  audio.addEventListener('pause',   function() { setState('paused');  });
  audio.addEventListener('error',   function() { setState('error');   });
  audio.addEventListener('stalled', function() { setState('stalled'); });
  audio.addEventListener('waiting', function() {
    statusEl.textContent = 'Mise en mémoire tampon…';
    statusEl.className   = 'radio-status is-loading';
  });
  audio.addEventListener('canplay', function() {
    if (statusEl.classList.contains('is-loading')) {
      statusEl.textContent = '';
      statusEl.className   = 'radio-status';
    }
  });

  /* Volume avec persistance localStorage */
  if (volEl) {
    volEl.addEventListener('input', function() {
      var vol = parseFloat(volEl.value);
      audio.volume = vol;
      localStorage.setItem('radio_volume', vol);
    });
  }

})();
