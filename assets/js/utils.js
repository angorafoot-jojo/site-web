/* ============================================================
   assets/js/utils.js — Fonctions utilitaires partagées
   Exposées sur window.EduRoyaume.*
   ============================================================ */
(function (global) {
  'use strict';

  /**
   * Protection XSS : échappe les caractères HTML dangereux.
   * À utiliser sur toute valeur insérée via innerHTML.
   * @param {*} s
   * @returns {string}
   */
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  /**
   * Formate une durée en secondes en "M:SS".
   * @param {number} seconds
   * @returns {string}
   */
  function formatDuration(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const m   = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return m + ':' + String(sec).padStart(2, '0');
  }

  /**
   * Emprisonne le focus dans un conteneur (modale, drawer, etc.).
   * À appeler dans un écouteur keydown sur le document lorsque la modale est ouverte.
   *
   * @param {HTMLElement} container  — élément racine de la modale
   * @param {KeyboardEvent} e        — événement keydown
   *
   * Exemple d'usage :
   *   document.addEventListener('keydown', function(e) {
   *     if (e.key === 'Tab' && modal.classList.contains('open')) {
   *       EduRoyaume.trapFocus(modal, e);
   *     }
   *   });
   */
  function trapFocus(container, e) {
    var FOCUSABLE = 'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';
    var nodes = Array.from(container.querySelectorAll(FOCUSABLE))
      .filter(function(el) { return el.offsetParent !== null; }); /* exclure les éléments cachés */
    if (!nodes.length) return;
    var first = nodes[0];
    var last  = nodes[nodes.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
    }
  }

  /* ── Namespace global ───────────────────────────────────── */
  global.EduRoyaume            = global.EduRoyaume || {};
  global.EduRoyaume.escapeHtml    = escapeHtml;
  global.EduRoyaume.formatDuration = formatDuration;
  global.EduRoyaume.trapFocus      = trapFocus;

})(window);
