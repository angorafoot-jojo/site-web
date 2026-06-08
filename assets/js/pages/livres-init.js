/* assets/js/pages/livres-init.js
   Initialisation du catalogue de livres.
   Dépendances : utils.js, book-catalogue.js, epub-reader.js */
(function () {
  'use strict';

  EduRoyaume.BookCatalogue.init({
    dataUrl    : 'assets/data/books.json',
    gridId     : 'book-grid',
    countId    : 'lib-results-count',
    searchId   : 'lib-search',
    sortId     : 'select-sort',
    dispoId    : 'select-dispo',
    langId     : 'select-lang',
    singular   : 'livre',
    plural     : 'livres',
    openFnName : 'openBook',
    availFn    : function (b) { return !!(b.epub || b.pdf); },
    isEnFn     : function (b) { return b.tags && b.tags.includes('en'); },
    errorMsg   : 'Impossible de charger la bibliothèque.',
  });

  window.openBook = function (id) {
    var item = EduRoyaume.BookCatalogue.find('book-grid', id);
    if (item) EduRoyaume.EpubReader.open(item);
  };
})();
