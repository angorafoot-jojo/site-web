/* assets/js/pages/podcasts-init.js
   Initialisation du lecteur podcast de la page podcasts.html.
   Dépendances : utils.js, media-player.js (chargés avant ce fichier) */
(function () {
  'use strict';

  EduRoyaume.MediaPlayer.init({
    dataUrl       : 'assets/data/podcasts.json',
    icon          : '#icon-mic',
    labelSingular : 'épisode',
    labelPlural   : 'épisodes',
  });
})();
