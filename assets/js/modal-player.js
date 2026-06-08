/* ============================================================
   assets/js/modal-player.js — Modale vidéo/audio (YouTube + Drive)
   Utilisé par : louange.html

   Dépendances : aucune (standalone)

   Usage :
     Les cartes .cantique-card portent des data-attributes :
       data-type  : "yt" | "drive"
       data-id    : ID YouTube ou Drive
       data-title : titre affiché dans la modale
   ============================================================ */

(function () {
  'use strict';

  var modal        = document.getElementById('mediaModal');
  var modalTitle   = document.getElementById('modalTitle');
  var modalContent = document.getElementById('modalContent');
  var modalClose   = document.getElementById('modalClose');

  if (!modal) return; /* sécurité : page sans modale */

  /* ── Ouvrir ─────────────────────────────────────────────────── */
  function openModal(type, id, title) {
    modalTitle.textContent = title;

    if (type === 'yt') {
      modalContent.innerHTML =
        '<div class="media-modal-yt">' +
          '<iframe src="https://www.youtube.com/embed/' + encodeURIComponent(id) + '?autoplay=1&rel=0" ' +
          'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" ' +
          'allowfullscreen loading="lazy"></iframe>' +
        '</div>';
    } else {
      /* Google Drive video — même conteneur 16:9 que YouTube */
      modalContent.innerHTML =
        '<div class="media-modal-yt">' +
          '<iframe src="https://drive.google.com/file/d/' + encodeURIComponent(id) + '/preview" ' +
          'allow="autoplay" allowfullscreen loading="lazy"></iframe>' +
        '</div>';
    }

    modal.classList.add('open');
    document.body.style.overflow = 'hidden';

    /* Focus sur le bouton fermer pour accessibilité */
    setTimeout(function() { if (modalClose) modalClose.focus(); }, 80);
  }

  /* ── Fermer ─────────────────────────────────────────────────── */
  function closeModal() {
    modal.classList.remove('open');
    modalContent.innerHTML = ''; /* arrête la lecture */
    document.body.style.overflow = '';
  }

  /* ── Cartes ─────────────────────────────────────────────────── */
  document.querySelectorAll('.cantique-card').forEach(function(card) {
    function activate() {
      openModal(card.dataset.type, card.dataset.id, card.dataset.title);
    }
    card.addEventListener('click', activate);
    card.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(); }
    });
  });

  /* ── Contrôles modale ───────────────────────────────────────── */
  modalClose.addEventListener('click', closeModal);
  modal.addEventListener('click', function(e) { if (e.target === modal) closeModal(); });

  /* Fermer sur Escape */
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });

})();
