/* assets/js/pages/index-init.js
   Scripts de la page d'accueil (index.html) :
     1. Carrousel hero (vslider)
     2. Rotation des thèmes hero
     3. Lecteur radio sticky
   (La dernière vidéo et les articles récents vivent désormais
   sur nouveau.html — voir assets/js/pages/nouveau-init.js.)
   Dépendances : utils.js (chargé avant ce fichier) */

(function () {
  'use strict';

  /* ── 1. Carrousel hero (vslider) ────────────────────────────── */
  (function () {
    var slides = document.querySelectorAll('.vslide');
    var dots   = document.querySelectorAll('.vslider-dot');
    if (!slides.length) return;
    var cur = 0, timer;

    function goTo(n) {
      slides[cur].classList.remove('active');
      dots[cur].classList.remove('active');
      cur = (n + slides.length) % slides.length;
      slides[cur].classList.add('active');
      dots[cur].classList.add('active');
    }

    function startAuto() { timer = setInterval(function () { goTo(cur + 1); }, 7000); }
    function stopAuto()  { clearInterval(timer); }

    var prev = document.querySelector('.vslider-prev');
    var next = document.querySelector('.vslider-next');
    if (prev) prev.addEventListener('click', function () { stopAuto(); goTo(cur - 1); startAuto(); });
    if (next) next.addEventListener('click', function () { stopAuto(); goTo(cur + 1); startAuto(); });
    dots.forEach(function (d, i) {
      d.addEventListener('click', function () { stopAuto(); goTo(i); startAuto(); });
    });

    var section = document.querySelector('.vslider');
    if (section) {
      section.addEventListener('mouseenter', stopAuto);
      section.addEventListener('mouseleave', startAuto);
    }

    startAuto();
  })();

  /* ── 2. Rotation des thèmes hero ────────────────────────────── */
  (function () {
    var themes = document.querySelectorAll('.hero-theme');
    if (!themes.length) return;
    var current = 0;
    setInterval(function () {
      themes[current].classList.remove('active');
      current = (current + 1) % themes.length;
      themes[current].classList.add('active');
    }, 4000);
  })();

  /* ── 3. Lecteur radio sticky ─────────────────────────────────── */
  (function () {
    var player   = document.getElementById('radio-player');
    var audio    = document.getElementById('radio-audio');
    var playBtn  = document.getElementById('radio-play-btn');
    var closeBtn = document.getElementById('radio-close-btn');
    var volSlider= document.getElementById('radio-vol');
    var radioIcon= document.getElementById('radio-icon');
    var heroBtn  = document.getElementById('btn-radio-live');

    if (!player || !audio || !playBtn) return;

    var PLAY_PATH  = 'M8 5v14l11-7z';
    var PAUSE_PATH = 'M6 19h4V5H6v14zm8-14v14h4V5h-4z';

    function setPlaying(isPlaying) {
      var pathEl = radioIcon && radioIcon.querySelector('path');
      if (pathEl) pathEl.setAttribute('d', isPlaying ? PAUSE_PATH : PLAY_PATH);
      playBtn.setAttribute('aria-label',  isPlaying ? 'Mettre en pause' : 'Lancer la radio');
      playBtn.setAttribute('aria-pressed', isPlaying ? 'true' : 'false');
    }

    function openPlayer() {
      player.hidden = false;
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { player.classList.add('is-visible'); });
      });
      audio.play().then(function () { setPlaying(true); }).catch(function () {});
    }

    if (heroBtn) heroBtn.addEventListener('click', openPlayer);

    playBtn.addEventListener('click', function () {
      if (audio.paused) {
        audio.play().then(function () { setPlaying(true); }).catch(function () {});
      } else {
        audio.pause();
        setPlaying(false);
      }
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        player.classList.remove('is-visible');
        audio.pause();
        audio.currentTime = 0;
        setPlaying(false);
        setTimeout(function () { player.hidden = true; }, 350);
      });
    }

    if (volSlider) {
      volSlider.addEventListener('input', function () {
        audio.volume = parseFloat(volSlider.value);
      });
    }

    audio.addEventListener('play',  function () { setPlaying(true); });
    audio.addEventListener('pause', function () { setPlaying(false); });
  })();

})();
