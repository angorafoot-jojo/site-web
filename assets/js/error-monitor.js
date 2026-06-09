/* ============================================================
   assets/js/error-monitor.js — Surveillance des erreurs JS
   Chargé automatiquement par nav.js sur toutes les pages.

   Mode sans Sentry (par défaut) :
     Les erreurs sont loggées dans la console avec un préfixe [EduRoyaume].
     Rien n'est envoyé à l'extérieur.

   Mode Sentry (optionnel) :
     1. Créer un compte sur https://sentry.io (gratuit — 5 000 erreurs/mois)
     2. Créer un projet de type "Browser JavaScript"
     3. Copier votre DSN (ex: https://abc123@o12345.ingest.sentry.io/67890)
     4. Dans nav.js, remplacer la valeur de SENTRY_DSN par votre DSN
        (chercher "SENTRY_DSN" dans nav.js)

   Erreurs capturées :
     - Crashes JavaScript non gérés (window.onerror)
     - Promesses rejetées non gérées (unhandledrejection)
     - Erreurs spécifiques : EPUB, lecteur audio, chargement JSON

   Erreurs ignorées (bruit) :
     - Extensions navigateur (chrome-extension://, moz-extension://)
     - "Script error." cross-origin (scripts tiers non contrôlés)
     - ResizeObserver (avertissement inoffensif du navigateur)
     - Erreurs réseau de l'utilisateur (fetch aborted, network error)
   ============================================================ */

(function (global) {
  'use strict';

  /* ── Vérifier si le monitoring est activé ─────────────────── */
  var ns  = global.EduRoyaume = global.EduRoyaume || {};
  var cfg = ns.config         = ns.config         || {};

  /* ── Filtre : faut-il ignorer cette erreur ? ──────────────── */
  function shouldIgnore(message, source) {
    if (!message) return true;

    /* Erreurs d'extensions navigateur */
    if (source && (
      source.indexOf('chrome-extension://') !== -1 ||
      source.indexOf('moz-extension://')    !== -1 ||
      source.indexOf('safari-extension://')  !== -1
    )) return true;

    /* Erreur cross-origin sans détail (bloquée par CORS) */
    if (message === 'Script error.' || message === 'Script error') return true;

    /* ResizeObserver — inoffensif, déclenché par le navigateur lui-même */
    if (message.indexOf('ResizeObserver') !== -1) return true;

    /* Erreurs réseau pures (problème côté utilisateur) */
    if (
      message.indexOf('NetworkError')      !== -1 ||
      message.indexOf('Failed to fetch')   !== -1 ||
      message.indexOf('Load failed')       !== -1 ||
      message.indexOf('fetch is aborted')  !== -1 ||
      message.indexOf('The operation was aborted') !== -1
    ) return true;

    return false;
  }

  /* ── Enrichir l'erreur avec le contexte page ──────────────── */
  function buildContext(extra) {
    return Object.assign({
      page    : global.location && global.location.pathname,
      userAgent: navigator && navigator.userAgent,
    }, extra || {});
  }

  /* ── Rapporter une erreur ─────────────────────────────────── */
  function report(message, extra) {
    var ctx = buildContext(extra);

    /* Mode console (toujours actif) */
    console.warn('[EduRoyaume] Erreur capturée :', message, ctx);

    /* Mode Sentry (si DSN configuré et SDK chargé) */
    if (global.Sentry) {
      try {
        global.Sentry.withScope(function(scope) {
          if (ctx.page)      scope.setTag('page', ctx.page);
          if (ctx.component) scope.setTag('component', ctx.component);
          if (ctx.url)       scope.setContext('media', { url: ctx.url });
          global.Sentry.captureMessage(message, 'error');
        });
      } catch (e) { /* ne pas planter si Sentry est défaillant */ }
    }
  }

  /* ── Capturer les erreurs JS globales ─────────────────────── */
  global.addEventListener('error', function(event) {
    var msg = event.message || String(event.error);
    if (shouldIgnore(msg, event.filename)) return;

    report(msg, {
      source : event.filename,
      line   : event.lineno,
      col    : event.colno,
    });
  });

  /* ── Capturer les promesses rejetées non gérées ───────────── */
  global.addEventListener('unhandledrejection', function(event) {
    var reason = event.reason;
    var msg = (reason instanceof Error)
      ? reason.message
      : String(reason);

    if (shouldIgnore(msg, '')) return;

    report('Promesse rejetée : ' + msg, {
      stack: (reason instanceof Error) ? reason.stack : undefined,
    });
  });

  /* ── API publique : signaler une erreur métier ────────────── */

  /**
   * Signaler une erreur depuis n'importe quel module du site.
   * @param {string}  message    — description courte
   * @param {object}  [extra]    — contexte : component, url, etc.
   *
   * Exemples :
   *   EduRoyaume.reportError('EPUB non chargé', { component:'epub-reader', url: item.epub });
   *   EduRoyaume.reportError('Audio indisponible', { component:'media-player', url: src });
   */
  ns.reportError = report;

  /* ── Charger le SDK Sentry si DSN configuré ───────────────── */
  var dsn = cfg.sentryDsn;
  if (dsn && typeof dsn === 'string' && dsn.indexOf('sentry.io') !== -1) {
    var script   = document.createElement('script');
    script.src   = 'https://browser.sentry-cdn.com/8.45.1/bundle.min.js';
    script.async = true;
    script.setAttribute('crossorigin', 'anonymous');
    script.onload = function() {
      if (!global.Sentry) return;
      global.Sentry.init({
        dsn             : dsn,
        environment     : global.location.hostname === 'localhost' ? 'development' : 'production',
        release         : cfg.version || '1.0.0',
        /* Capturer uniquement les erreurs les plus importantes */
        sampleRate      : 1.0,
        /* Ignorer les mêmes URLs que notre filtre manuel */
        denyUrls        : [
          /chrome-extension:\/\//,
          /moz-extension:\/\//,
          /safari-extension:\/\//,
        ],
        ignoreErrors    : [
          'ResizeObserver loop',
          'Script error',
          'NetworkError',
          'Failed to fetch',
          'Load failed',
        ],
        beforeSend: function(event) {
          /* Ne pas envoyer en développement local */
          if (global.location.hostname === 'localhost') return null;
          return event;
        },
      });
      console.info('[EduRoyaume] Sentry initialisé (', dsn.slice(0, 30) + '...', ')');
    };
    script.onerror = function() {
      console.warn('[EduRoyaume] Sentry SDK non chargé — monitoring console uniquement.');
    };
    /* Insérer après le script courant, sans bloquer le rendu */
    document.currentScript
      ? document.currentScript.parentNode.insertBefore(script, document.currentScript.nextSibling)
      : document.head.appendChild(script);
  }

})(window);
