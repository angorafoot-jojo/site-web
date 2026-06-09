/* assets/js/pages/index-init.js
   Scripts de la page d'accueil (index.html) :
     1. Carrousel hero (vslider)
     2. Rotation des thèmes hero
     3. Dernière vidéo YouTube (rss2json)
     4. Articles récents (articles.json)
     5. Lecteur radio sticky
   Dépendances : utils.js (chargé avant ce fichier) */

(function () {
  'use strict';

  var esc = (window.EduRoyaume && window.EduRoyaume.escapeHtml)
    ? window.EduRoyaume.escapeHtml
    : function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };

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

  /* ── 3. Dernière vidéo YouTube ──────────────────────────────── */
  (function () {
    var CHANNEL = 'UCycAoa7k7LqyvG_TQWlG5_g';
    var API = 'https://api.rss2json.com/v1/api.json?rss_url='
      + encodeURIComponent('https://www.youtube.com/feeds/videos.xml?channel_id=' + CHANNEL);

    fetch(API)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var v = data.items && data.items[0];
        if (!v) return;

        var videoId = v.link.indexOf('v=') !== -1
          ? v.link.split('v=')[1].split('&')[0]
          : v.guid.split(':').pop();

        var videoUrl = 'https://www.youtube.com/watch?v=' + videoId;
        var thumbUrl = 'https://img.youtube.com/vi/' + videoId + '/hqdefault.jpg';
        var pubDate  = new Date(v.pubDate).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' });

        var tmpDiv = document.createElement('div');
        tmpDiv.innerHTML = v.description || '';
        var desc = (tmpDiv.textContent || tmpDiv.innerText || '').trim().slice(0, 220);

        var featuredTitle = document.getElementById('featured-title');
        var ytDate        = document.getElementById('yt-date');
        var ytDesc        = document.getElementById('yt-desc');
        var ytThumb       = document.getElementById('yt-thumb');
        var ytLink        = document.getElementById('yt-link');
        var ytThumbLink   = document.getElementById('yt-thumb-link');

        if (featuredTitle) featuredTitle.textContent = v.title;
        if (ytDate)        ytDate.textContent        = pubDate;
        if (ytDesc)        ytDesc.textContent        = desc + (desc.length === 220 ? '…' : '');
        if (ytThumb)       { ytThumb.src = thumbUrl; ytThumb.alt = v.title; }
        if (ytLink)        ytLink.href        = videoUrl;
        if (ytThumbLink)   ytThumbLink.href   = videoUrl;
      })
      .catch(function () {
        var featuredTitle = document.getElementById('featured-title');
        var ytDesc        = document.getElementById('yt-desc');
        if (featuredTitle) featuredTitle.textContent = 'Dernier message';
        if (ytDesc)        ytDesc.textContent = 'Consultez notre chaîne YouTube pour le dernier enseignement.';
      });
  })();

  /* ── 4. Articles récents ─────────────────────────────────────── */
  (function () {
    var CAT_LABELS = { vie: 'Vie chrétienne', meditation: 'Méditation', royaume: 'Royaume', eschatologie: 'Eschatologie' };
    var CAT_TAGS   = { vie: 'tag-navy', meditation: 'tag-gold', royaume: 'tag-wine', eschatologie: 'tag-wine' };

    fetch('assets/data/articles.json')
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (articles) {
        /* Priorité aux articles marqués featured:true, sinon les 3 plus récents */
        var featured = articles.filter(function (a) { return a.featured && !a.en; });
        var recent = featured.length >= 3
          ? featured.slice(0, 3)
          : articles
              .filter(function (a) { return !a.en; })
              .sort(function (a, b) { return b.year - a.year || b.id - a.id; })
              .slice(0, 3);

        var grid = document.getElementById('home-articles-grid');
        if (!grid) return;
        grid.innerHTML = recent.map(function (a, i) {
          var label    = CAT_LABELS[a.cat] || esc(a.cat);
          var tagCls   = CAT_TAGS[a.cat]   || 'tag-navy';
          var featured = i === 0 ? 'article-featured' : '';
          return '<article class="article-card ' + featured + '" data-animate data-delay="' + (i + 1) + '" role="listitem">'
            + '<div class="article-thumb">'
              + '<div class="article-thumb-cover gc-' + esc(String(a.color)) + '">'
                + '<span class="article-thumb-cover-title">' + esc(a.title) + '</span>'
              + '</div>'
            + '</div>'
            + '<div class="article-body">'
              + '<span class="tag ' + tagCls + '">' + label + '</span>'
              + '<h3>' + esc(a.title) + '</h3>'
              + '<div class="article-footer">'
                + '<span>' + esc(String(a.year)) + '</span>'
                + '<a href="articles.html" class="read-more">'
                  + 'Lire'
                  + '<svg width="14" height="14" aria-hidden="true"><use href="#icon-arrow-right"/></svg>'
                + '</a>'
              + '</div>'
            + '</div>'
          + '</article>';
        }).join('');
      })
      .catch(function (e) { console.error('articles.json load error:', e); });
  })();

  /* ── 5. Lecteur radio sticky ─────────────────────────────────── */
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
