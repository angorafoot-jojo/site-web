/* assets/js/pages/articles-init.js
   Initialisation du catalogue d'articles.
   Dépendances : utils.js, book-catalogue.js, epub-reader.js */
(function () {
  'use strict';

  EduRoyaume.BookCatalogue.init({
    dataUrl    : 'assets/data/articles.json',
    gridId     : 'art-grid',
    countId    : 'lib-results-count',
    searchId   : 'lib-search',
    sortId     : 'select-sort',
    dispoId    : 'select-dispo',
    catId      : 'select-cat',
    singular   : 'article',
    plural     : 'articles',
    openFnName : 'openArticle',
    availFn    : function (a) { return !!(a.epub || a.pdf); },
    isEnFn     : function (a) { return !!a.en; },
    errorMsg   : 'Impossible de charger les articles.',
  });

  window.openArticle = function (id) {
    var item = EduRoyaume.BookCatalogue.find('art-grid', id);
    if (item) EduRoyaume.EpubReader.open(item);
  };
})();
