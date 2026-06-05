/* ═══════════════════════════════════════════════════
   ARTICLES DATA — partagé entre articles.html et index.html
   cat: eschatologie | vie | meditation | royaume
   color: 1-8 gradient preset
   en: true → article en anglais
═══════════════════════════════════════════════════ */
const ARTICLES = [
  { id: 1, title:'Confession de la Parole de foi et de liberté',               color:1, cat:'vie',         year:2024,
    epub:'assets/articles/1.epub', pdf:'https://levangileduroyaume.com/wp-content/uploads/2024/07/CONFESSION-DE-LA-PAROLE-DE-FOI-ET-DE-LIBERTE-version-francaise.pdf' },
  { id: 2, title:'La grandeur de Dieu et la fragilité de l\'homme',            color:6, cat:'meditation',   year:2024,
    epub:'assets/articles/2.epub', pdf:'https://levangileduroyaume.com/wp-content/uploads/2024/07/LA-GRANDEUR-DE-DIEU-ET-LA-FRAGILITE-DE-LHOMME1.pdf' },
  { id: 3, title:'Le temps de remettre les choses en ordre',                   color:1, cat:'royaume',      year:2024,
    epub:'assets/articles/3.epub', pdf:'https://levangileduroyaume.com/wp-content/uploads/2024/06/LE-TEMPS-DE-REMETTRE-LES-CHOSES-EN-ORDRE.pdf' },
  { id: 4, title:'The Time of Putting All Things Straight',                    color:1, cat:'royaume',      year:2024, en:true,
    epub:'assets/articles/4.epub', pdf:'https://levangileduroyaume.com/wp-content/uploads/2024/06/THE-TIME-OF-PUTTING-ALL-THINGS-STRAIGHT.pdf' },
  { id: 5, title:'Des Antichrists et du corps ayant la charge de les détruire',color:5, cat:'eschatologie', year:2024,
    epub:'assets/articles/5.epub', pdf:'https://levangileduroyaume.com/wp-content/uploads/2024/06/DES-ANTICHRISTS-ET-DU-CORPS-AYANT-LA-CHARGE-DE-LES-DETRUIRE.pdf' },
  { id: 6, title:'Of Antichrists and of a Body That Destroys Them',            color:5, cat:'eschatologie', year:2024, en:true,
    epub:'assets/articles/6.epub', pdf:'https://levangileduroyaume.com/wp-content/uploads/2024/06/OF-ANTICHRISTS-AND-A-BODY-THAT-DESTROYS-THEM.pdf' },
  { id: 7, title:'Le Combat Spirituel',                                        color:3, cat:'vie',         year:2021,
    epub:'assets/articles/7.epub', pdf:'https://levangileduroyaume.com/wp-content/uploads/2021/04/LE-COMBAT-SPIRITUEL.pdf' },
  { id: 8, title:'Vous devez naître de nouveau',                               color:3, cat:'vie',        year:2021,
    epub:'assets/articles/8.epub', pdf:'assets/pdfs/articles/vous-devez-naitre-de-nouveau.pdf' },
  { id: 9, title:'Vivre le mariage : le modèle de Christ et l\'Église',        color:8, cat:'vie',        year:2021,
    epub:'assets/articles/9.epub', pdf:'assets/pdfs/articles/vivre-le-mariage-modele-christ.pdf' },
  { id:10, title:'Se marier : le modèle de Christ et l\'Église',               color:8, cat:'vie',        year:2021,
    epub:'assets/articles/10.epub', pdf:'assets/pdfs/articles/se-marier-modele-christ.pdf' },
  { id:11, title:'Pourquoi beaucoup de chrétiens sont-ils lents à comprendre ?', color:4, cat:'vie',      year:2020,
    epub:'assets/articles/11.epub', pdf:'assets/pdfs/articles/pourquoi-chretiens-lents-comprendre.pdf' },
  { id:12, title:'Ayons la justice de Dieu pour être sauvés de la mort',       color:3, cat:'vie',        year:2020,
    epub:'assets/articles/12.epub', pdf:'assets/pdfs/articles/ayons-la-justice-de-dieu.pdf' },
  { id:13, title:'Comment allumer les lampes du chandelier ?',                 color:6, cat:'meditation', year:2020,
    epub:'assets/articles/13.epub', pdf:'assets/pdfs/articles/comment-allumer-lampes-chandelier.pdf' },
  { id:14, title:'Le mystère de Christ',                                       color:7, cat:'royaume',    year:2020,
    epub:'assets/articles/14.epub', pdf:'assets/pdfs/articles/le-mystere-de-christ.pdf' },
  { id:15, title:'Le renoncement aux œuvres mortes : les doctrines fondamentales', color:2, cat:'vie',   year:2020,
    epub:'assets/articles/15.epub', pdf:'assets/pdfs/articles/le-renoncement-aux-oeuvres-mortes.pdf' },
  { id:16, title:'Le Salut',                                                   color:5, cat:'vie',        year:2020,
    epub:'assets/articles/16.epub', pdf:'assets/pdfs/articles/le-salut.pdf' },
];
