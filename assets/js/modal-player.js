/* ============================================================
   assets/js/modal-player.js — Modale vidéo/audio (YouTube + Drive)
   Utilisé par : louange.html

   Dépendances : aucune (standalone)

   Usage :
     Les cartes .cantique-card portent des data-attributes :
       data-type  : "yt" | "drive"
       data-id    : ID YouTube ou Drive
       data-title : titre affiché dans la modale

   Sécurité :
     - Les IDs sont validés par regex avant utilisation
     - L'iframe est créé via createElement (pas innerHTML)
     - Tout ID invalide est rejeté silencieusement
   ============================================================ */

(function () {
  'use strict';

  var modal        = document.getElementById('mediaModal');
  var modalTitle   = document.getElementById('modalTitle');
  var modalContent = document.getElementById('modalContent');
  var modalClose   = document.getElementById('modalClose');

  if (!modal) return; /* sécurité : page sans modale */

  /* ── Focus restoration ──────────────────────────────────────── */
  var _focusBeforeOpen = null; /* mémorise l'élément actif avant l'ouverture */

  /* ── Validation des IDs ─────────────────────────────────────── */
  var RE_YT    = /^[a-zA-Z0-9_-]{11}$/;
  var RE_DRIVE = /^[a-zA-Z0-9_-]{28,}$/;

  function isValidId(type, id) {
    if (typeof id !== 'string') return false;
    return type === 'yt' ? RE_YT.test(id) : RE_DRIVE.test(id);
  }

  /* ── Construire l'iframe via createElement ─────────────────── */
  function buildIframe(type, id) {
    var iframe = document.createElement('iframe');
    iframe.setAttribute('loading', 'lazy');
    iframe.setAttribute('allowfullscreen', '');

    if (type === 'yt') {
      iframe.src = 'https://www.youtube.com/embed/' + id + '?autoplay=1&rel=0';
      iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
    } else {
      iframe.src = 'https://drive.google.com/file/d/' + id + '/preview';
      iframe.allow = 'autoplay';
    }

    return iframe;
  }

  /* ── Ouvrir ─────────────────────────────────────────────────── */
  function openModal(type, id, title) {
    /* Rejet silencieux si l'ID ne correspond pas au pattern attendu */
    if (!isValidId(type, id)) {
      console.warn('modal-player: ID rejeté (pattern invalide) :', type, id);
      return;
    }

    modalTitle.textContent = title || '';

    /* Vider le contenu précédent */
    while (modalContent.firstChild) {
      modalContent.removeChild(modalContent.firstChild);
    }

    /* Wrapper 16:9 avec spinner + iframe */
    var wrapper = document.createElement('div');
    wrapper.className = 'media-modal-yt';

    /* Spinner — retiré automatiquement quand l'iframe répond */
    var spinner = document.createElement('div');
    spinner.className = 'modal-loading';
    spinner.setAttribute('aria-hidden', 'true');
    wrapper.appendChild(spinner);

    var iframe = buildIframe(type, id);
    iframe.addEventListener('load', function () {
      var loading = wrapper.querySelector('.modal-loading');
      if (loading) loading.parentNode.removeChild(loading);
    });
    wrapper.appendChild(iframe);
    modalContent.appendChild(wrapper);

    /* Lien de secours pour les bloqueurs / restrictions régionales */
    var fallbackUrl = type === 'yt'
      ? 'https://youtu.be/' + id
      : 'https://drive.google.com/file/d/' + id + '/view';
    var fallback = document.createElement('a');
    fallback.className    = 'modal-fallback-link';
    fallback.href         = fallbackUrl;
    fallback.target       = '_blank';
    fallback.rel          = 'noopener noreferrer';
    fallback.textContent  = type === 'yt' ? 'Ouvrir sur YouTube ↗' : 'Ouvrir sur Drive ↗';
    modalContent.appendChild(fallback);

    /* Mémoriser le focus avant ouverture pour le restaurer à la fermeture */
    _focusBeforeOpen = document.activeElement;

    modal.classList.add('open');
    document.body.style.overflow = 'hidden';

    /* Focus sur le bouton fermer (premier élément focusable) */
    setTimeout(function() { if (modalClose) modalClose.focus(); }, 80);
  }

  /* ── Fermer ─────────────────────────────────────────────────── */
  function closeModal() {
    modal.classList.remove('open');
    /* Vider via DOM pour arrêter la lecture */
    while (modalContent.firstChild) {
      modalContent.removeChild(modalContent.firstChild);
    }
    document.body.style.overflow = '';
    /* Restaurer le focus sur l'élément qui avait le focus avant l'ouverture */
    if (_focusBeforeOpen && typeof _focusBeforeOpen.focus === 'function') {
      _focusBeforeOpen.focus();
      _focusBeforeOpen = null;
    }
  }

  /* ── Délégation d'événements sur le conteneur ──────────────────
     Fonctionne avec les cartes injectées dynamiquement (louange.json).  */
  document.addEventListener('click', function(e) {
    var card = e.target.closest('.cantique-card');
    if (!card) return;
    openModal(card.dataset.type, card.dataset.id, card.dataset.title);
  });
  /* Note : pas de keydown sur .cantique-card — c'est désormais un <button>,
     le navigateur déclenche nativement un clic sur Enter et Space. */

  /* ── Contrôles modale ───────────────────────────────────────── */
  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', function(e) { if (e.target === modal) closeModal(); });

  /* Clavier : Escape ferme la modale, Tab reste emprisonné dans la modale */
  document.addEventListener('keydown', function(e) {
    if (!modal.classList.contains('open')) return;
    if (e.key === 'Escape') { closeModal(); return; }
    if (e.key === 'Tab' && window.EduRoyaume && window.EduRoyaume.trapFocus) {
      window.EduRoyaume.trapFocus(modal, e);
    }
  });

})();
