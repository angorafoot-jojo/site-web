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

  /* ── Namespace global ───────────────────────────────────── */
  global.EduRoyaume            = global.EduRoyaume || {};
  global.EduRoyaume.escapeHtml    = escapeHtml;
  global.EduRoyaume.formatDuration = formatDuration;

})(window);
