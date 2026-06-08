/* ============================================================
   nav.js — Header, footer et menu mobile partagés
   Placé en premier dans <body> sans defer → injection synchrone,
   aucun flash de contenu non stylé.
   ============================================================ */
(function () {
  'use strict';

  /* ── Config ─────────────────────────────────────────────────*/
  /* Pages sans footer global (lecteur plein écran ou expérience immersive) */
  var NO_FOOTER = ['articles', 'livres', 'radio'];

  /* Correspondance page → clé de navigation active */
  var ACTIVE_MAP = {
    'index'          : 'accueil',
    'radio'          : 'ecouter',
    'audios'         : 'ecouter',
    'podcasts'       : 'ecouter',
    'videos'         : 'regarder',
    'articles'       : 'lire',
    'livres'         : 'lire',
    'louange'        : 'louange',
  };

  /* ── SVG Sprite — toutes les icônes du site ─────────────────*/
  var SVG_SPRITE = '<svg xmlns="http://www.w3.org/2000/svg" aria-hidden="true" style="display:none">'
    + '<symbol id="icon-video" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></symbol>'
    + '<symbol id="icon-audio" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z"/><path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></symbol>'
    + '<symbol id="icon-podcast" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></symbol>'
    + '<symbol id="icon-livre" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></symbol>'
    + '<symbol id="icon-article" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></symbol>'
    + '<symbol id="icon-cantique" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></symbol>'
    + '<symbol id="icon-radio" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></symbol>'
    + '<symbol id="icon-mail" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></symbol>'
    + '<symbol id="icon-globe" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></symbol>'
    + '<symbol id="icon-youtube" viewBox="0 0 24 24" fill="currentColor"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46a2.78 2.78 0 0 0-1.95 1.96A29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58A2.78 2.78 0 0 0 3.41 19.6C5.12 20 12 20 12 20s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.95A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02" fill="white"/></symbol>'
    + '<symbol id="icon-facebook" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></symbol>'
    + '<symbol id="icon-whatsapp" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M11.99 2C6.47 2 1.99 6.48 1.99 12c0 1.78.47 3.44 1.28 4.89L1.5 22l5.26-1.74C8.19 21.4 10.04 22 12 22c5.52 0 10-4.48 10-10S17.51 2 11.99 2zm.01 18c-1.72 0-3.34-.47-4.74-1.28l-.34-.2-3.12 1.03 1.05-3.04-.22-.37C3.47 14.97 3 13.55 3 12c0-4.97 4.03-9 9-9s9 4.03 9 9-4.03 9-9 9z"/></symbol>'
    + '<symbol id="icon-play" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></symbol>'
    + '<symbol id="icon-pause" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></symbol>'
    + '<symbol id="icon-skip-next" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></symbol>'
    + '<symbol id="icon-skip-prev" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></symbol>'
    + '<symbol id="icon-headphones" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z"/><path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></symbol>'
    + '<symbol id="icon-mic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></symbol>'
    + '<symbol id="icon-download" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></symbol>'
    + '<symbol id="icon-volume" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></symbol>'
    + '<symbol id="icon-arrow-right" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></symbol>'
    + '<symbol id="icon-arrow-left" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></symbol>'
    + '<symbol id="icon-book-open" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></symbol>'
    + '<symbol id="icon-scroll" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></symbol>'
    + '<symbol id="icon-external" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></symbol>'
    + '<symbol id="icon-chevron-down" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></symbol>'
    + '<symbol id="icon-chevron-up" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></symbol>'
    + '<symbol id="icon-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></symbol>'
    + '<symbol id="icon-film" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="17" x2="22" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/></symbol>'
    + '<symbol id="icon-target" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></symbol>'
    + '<symbol id="icon-users" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></symbol>'
    + '</svg>';

  /* ── Logo SVG (réutilisé dans header et footer) ─────────────*/
  var LOGO_SVG = '<svg class="logo-mark" viewBox="0 0 38 44" fill="none" aria-hidden="true">'
    + '<circle cx="19" cy="11" r="9" stroke="currentColor" stroke-width="1.8"/>'
    + '<path d="M10 11h18M10 7.5c2.5 1 5.5 1.5 9 1.5s6.5-.5 9-1.5M10 14.5c2.5-1 5.5-1.5 9-1.5s6.5.5 9 1.5" stroke="currentColor" stroke-width="1.1"/>'
    + '<path d="M19 2c-3 2.5-5 5.5-5 9s2 6.5 5 9M19 2c3 2.5 5 5.5 5 9s-2 6.5-5 9" stroke="currentColor" stroke-width="1.2"/>'
    + '<path d="M4 26a2 2 0 0 1 2-2h11v18H6a2 2 0 0 1-2-2V26z" stroke="currentColor" stroke-width="1.8"/>'
    + '<path d="M34 26a2 2 0 0 0-2-2H21v18h11a2 2 0 0 0 2-2V26z" stroke="currentColor" stroke-width="1.8"/>'
    + '<line x1="19" y1="24" x2="19" y2="42" stroke="currentColor" stroke-width="1.6"/>'
    + '<line x1="8" y1="30" x2="14" y2="30" stroke="currentColor" stroke-width="1" opacity=".5"/>'
    + '<line x1="8" y1="33" x2="14" y2="33" stroke="currentColor" stroke-width="1" opacity=".5"/>'
    + '<line x1="24" y1="30" x2="30" y2="30" stroke="currentColor" stroke-width="1" opacity=".5"/>'
    + '<line x1="24" y1="33" x2="30" y2="33" stroke="currentColor" stroke-width="1" opacity=".5"/>'
    + '</svg>';

  /* ── Header HTML ─────────────────────────────────────────── */
  var HEADER_HTML = '<header class="site-header" role="banner">'
    + '<div class="container">'
    + '<nav class="nav-inner" role="navigation" aria-label="Navigation principale">'
    + '<a href="index.html" class="logo" aria-label="L\'Évangile du Royaume — Accueil">'
    + LOGO_SVG
    + '<div class="logo-text"><span class="logo-title">L\'Évangile du Royaume</span><span class="logo-sub">La Bonne Nouvelle</span></div>'
    + '</a>'
    + '<ul class="nav-links" role="list">'
    + '<li class="nav-item"><a href="index.html" class="nav-link" data-nav="accueil">Accueil</a></li>'
    + '<li class="nav-item">'
    + '<a href="radio.html" class="nav-link" data-nav="ecouter" role="button" aria-haspopup="true">'
    + 'Écouter'
    + '<svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>'
    + '</a>'
    + '<ul class="dropdown" role="menu">'
    + '<li role="menuitem"><a href="radio.html" class="dropdown-link"><span class="dropdown-icon icon-bg-1"><svg width="18" height="18"><use href="#icon-radio"/></svg></span><span><strong style="display:block;font-size:.9rem">Radio en direct</strong><small style="opacity:.6">Parole Prophétique FM 24h/24</small></span></a></li>'
    + '<li role="menuitem"><a href="podcasts.html" class="dropdown-link"><span class="dropdown-icon icon-bg-3"><svg width="18" height="18"><use href="#icon-podcast"/></svg></span>Podcasts bibliques</a></li>'
    + '<li role="menuitem"><a href="audios.html" class="dropdown-link"><span class="dropdown-icon icon-bg-2"><svg width="18" height="18"><use href="#icon-audio"/></svg></span>Messages audio</a></li>'
    + '</ul>'
    + '</li>'
    + '<li class="nav-item"><a href="videos.html" class="nav-link" data-nav="regarder">Regarder</a></li>'
    + '<li class="nav-item">'
    + '<a href="articles.html" class="nav-link" data-nav="lire" role="button" aria-haspopup="true">'
    + 'Lire'
    + '<svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="14" height="14" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>'
    + '</a>'
    + '<ul class="dropdown" role="menu">'
    + '<li role="menuitem"><a href="articles.html" class="dropdown-link"><span class="dropdown-icon icon-bg-5"><svg width="18" height="18"><use href="#icon-article"/></svg></span>Articles &amp; Méditations</a></li>'
    + '<li role="menuitem"><a href="livres.html" class="dropdown-link"><span class="dropdown-icon icon-bg-4"><svg width="18" height="18"><use href="#icon-livre"/></svg></span>Livres</a></li>'
    + '</ul>'
    + '</li>'
    + '<li class="nav-item"><a href="louange.html" class="nav-link" data-nav="louange">Louange</a></li>'
    + '</ul>'
    + '<div class="nav-right">'
    + '<a href="radio.html" class="nav-live-badge" aria-label="Écouter la radio en direct">'
    + '<span class="live-dot" style="width:7px;height:7px;border-radius:50%;background:#4CAF50;display:inline-block;flex-shrink:0;animation:live-pulse 1.5s ease-in-out infinite"></span>'
    + 'Live'
    + '</a>'
    + '</div>'
    + '<button class="hamburger" aria-label="Ouvrir le menu" aria-expanded="false" aria-controls="mobile-menu">'
    + '<span></span><span></span><span></span>'
    + '</button>'
    + '</nav>'
    + '</div>'
    + '</header>';

  /* ── Mobile Menu HTML ────────────────────────────────────── */
  var MOBILE_HTML = '<nav class="mobile-menu" id="mobile-menu" role="navigation" aria-label="Menu mobile">'
    + '<a href="index.html" class="mobile-nav-link">Accueil</a>'
    + '<div class="mobile-nav-link" data-sub="mob-ecouter" role="button" tabindex="0">Écouter <svg class="m-chevron" style="width:18px;height:18px;transition:.3s" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg></div>'
    + '<ul class="mobile-sub" id="mob-ecouter">'
    + '<li><a href="radio.html" class="mobile-sub-link"><svg width="16" height="16"><use href="#icon-radio"/></svg> Radio en direct</a></li>'
    + '<li><a href="podcasts.html" class="mobile-sub-link"><svg width="16" height="16"><use href="#icon-podcast"/></svg> Podcasts</a></li>'
    + '<li><a href="audios.html" class="mobile-sub-link"><svg width="16" height="16"><use href="#icon-audio"/></svg> Audios</a></li>'
    + '</ul>'
    + '<a href="videos.html" class="mobile-nav-link">Regarder</a>'
    + '<div class="mobile-nav-link" data-sub="mob-lire" role="button" tabindex="0">Lire <svg class="m-chevron" style="width:18px;height:18px;transition:.3s" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg></div>'
    + '<ul class="mobile-sub" id="mob-lire">'
    + '<li><a href="articles.html" class="mobile-sub-link"><svg width="16" height="16"><use href="#icon-article"/></svg> Articles</a></li>'
    + '<li><a href="livres.html" class="mobile-sub-link"><svg width="16" height="16"><use href="#icon-livre"/></svg> Livres</a></li>'
    + '</ul>'
    + '<a href="louange.html" class="mobile-nav-link">Louange</a>'
    + '<div style="margin-top:2rem;display:flex;flex-direction:column;gap:.75rem">'
    + '<a href="radio.html" class="btn btn-ghost" style="justify-content:center"><span style="width:7px;height:7px;border-radius:50%;background:#4CAF50;display:inline-block"></span> Radio en direct</a>'
    + '</div>'
    + '</nav>'
    + '<div class="mobile-overlay" aria-hidden="true"></div>';

  /* ── Footer HTML ─────────────────────────────────────────── */
  var FOOTER_HTML = '<footer class="site-footer" role="contentinfo">'
    + '<div class="container">'
    + '<div class="footer-grid">'
    + '<div class="footer-brand">'
    + '<a href="index.html" class="logo" aria-label="Accueil" style="margin-bottom:1.25rem">'
    + LOGO_SVG
    + '<div class="logo-text"><span class="logo-title">L\'Évangile du Royaume</span><span class="logo-sub">La Bonne Nouvelle</span></div>'
    + '</a>'
    + '<p>Plateforme chrétienne francophone pour écouter des enseignements bibliques, podcasts et radio en direct.</p>'
    + '<nav class="social-links" aria-label="Réseaux sociaux">'
    + '<a href="https://www.youtube.com/channel/UCycAoa7k7LqyvG_TQWlG5_g" target="_blank" rel="noopener noreferrer" class="social-btn" aria-label="YouTube" style="color:#FF0000"><svg width="18" height="18"><use href="#icon-youtube"/></svg></a>'
    + '<a href="radio.html" class="social-btn" aria-label="Radio" style="color:#4CAF50"><svg width="18" height="18"><use href="#icon-radio"/></svg></a>'
    + '</nav>'
    + '</div>'
    + '<nav aria-label="Radio et audio"><h4>Radio et audio</h4><ul class="footer-links">'
    + '<li><a href="radio.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> Radio en direct</a></li>'
    + '<li><a href="podcasts.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> Séries podcast</a></li>'
    + '<li><a href="audios.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> Messages audio</a></li>'
    + '<li><a href="louange.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> Louanges</a></li>'
    + '</ul></nav>'
    + '<nav aria-label="Vidéos et lecture"><h4>Vidéos et lecture</h4><ul class="footer-links">'
    + '<li><a href="videos.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> Vidéos</a></li>'
    + '<li><a href="articles.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> Articles</a></li>'
    + '<li><a href="livres.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> Livres</a></li>'
    + '<li><a href="qui-sommes-nous.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> À propos</a></li>'
    + '<li><a href="nospartenaires.html" class="footer-link"><svg width="12" height="12"><use href="#icon-arrow-right"/></svg> Nos partenaires</a></li>'
    + '</ul></nav>'
    + '<address><h4>Contact</h4>'
    + '<div class="footer-contact-item"><div class="contact-icon"><svg width="16" height="16"><use href="#icon-mail"/></svg></div><a href="mailto:nousecrire@levangileduroyaume.com" style="color:inherit">nousecrire@levangileduroyaume.com</a></div>'
    + '<div class="footer-contact-item"><div class="contact-icon"><svg width="16" height="16"><use href="#icon-radio"/></svg></div><span>Parole Prophétique FM — <span style="color:#4CAF50">24h/24</span></span></div>'
    + '<div class="footer-contact-item"><div class="contact-icon"><svg width="16" height="16"><use href="#icon-globe"/></svg></div><span>Présence dans 43 pays</span></div>'
    + '</address>'
    + '</div>'
    + '<div class="footer-bottom">'
    + '<span>© 2025 L\'Évangile du Royaume. Tous droits réservés.</span>'
    + '<nav class="footer-bottom-links">'
    + '<a href="qui-sommes-nous.html">Qui sommes-nous</a>'
    + '<a href="confidentialite.html">Confidentialité</a>'
    + '</nav>'
    + '</div>'
    + '</div>'
    + '</footer>';

  /* ── Injection ───────────────────────────────────────────── */
  var page = document.body.getAttribute('data-page') || '';

  /* Synchrone : header avant tout rendu → évite le FOUC */
  document.body.insertAdjacentHTML('afterbegin', SVG_SPRITE + HEADER_HTML + MOBILE_HTML);

  /* Lien actif (le header vient d'être injecté, les liens existent déjà) */
  var navKey = ACTIVE_MAP[page];
  if (navKey) {
    var activeLink = document.querySelector('[data-nav="' + navKey + '"]');
    if (activeLink) activeLink.classList.add('active');
  }

  /* Footer : différé au DOMContentLoaded pour garantir l'insertion
     après tout le contenu de la page, pas après le script tag seul. */
  if (NO_FOOTER.indexOf(page) === -1) {
    document.addEventListener('DOMContentLoaded', function () {
      document.body.insertAdjacentHTML('beforeend', FOOTER_HTML);
    });
  }

})();
