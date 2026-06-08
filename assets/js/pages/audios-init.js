/* assets/js/pages/audios-init.js
   Initialisation du lecteur audio de la page audios.html.
   Dépendances : utils.js, media-player.js (chargés avant ce fichier) */
(function () {
  'use strict';

  EduRoyaume.MediaPlayer.init({
    dataUrl       : 'assets/data/audios.json',
    icon          : '#icon-headphones',
    labelSingular : 'partie',
    labelPlural   : 'parties',
    onLoaded      : function (items) {
      /* Met à jour le compteur CTA dynamiquement après chargement */
      var n = items.length;
      var strong = document.getElementById('cta-audio-strong');
      var span   = document.getElementById('cta-audio-span');
      if (strong) strong.textContent = n + ' messages audio';
      if (span)   span.textContent   = n + ' enseignements — cliquez pour écouter directement';
    },
  });
})();
