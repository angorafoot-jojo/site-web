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

    /* Wrapper 16:9 */
    var wrapper = document.createElement('div');
    wrapper.className = 'media-modal-yt';
    wrapper.appendChild(buildIframe(type, id));
    modalContent.appendChild(wrapper);

    modal.classList.add('open');
    document.body.style.overflow = 'hidden';

    /* Focus sur le bouton fermer pour accessibilité */
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
  }

  /* ── Délégation d'événements sur le conteneur ──────────────────
     Fonctionne avec les cartes injectées dynamiquement (louange.json).  */
  document.addEventListener('click', function(e) {
    var card = e.target.closest('.cantique-card');
    if (!card) return;
    openModal(card.dataset.type, card.dataset.id, card.dataset.title);
  });
  document.addEventListener('keydown', function(e) {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    var card = e.target.closest('.cantique-card');
    if (!card) return;
    e.preventDefault();
    openModal(card.dataset.type, card.dataset.id, card.dataset.title);
  });

  /* ── Contrôles modale ───────────────────────────────────────── */
  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', function(e) { if (e.target === modal) closeModal(); });

  /* Fermer sur Escape */
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });

})();
