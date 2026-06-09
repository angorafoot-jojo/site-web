/* ============================================================
   L'ÉVANGILE DU ROYAUME — Main JavaScript
   ============================================================ */

// ── Header scroll effect ─────────────────────────────────────
const header = document.querySelector('.site-header');
const onScroll = () => {
  header?.classList.toggle('scrolled', window.scrollY > 60);
};
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

// ── Mobile menu ──────────────────────────────────────────────
const hamburger   = document.querySelector('.hamburger');
const mobileMenu  = document.querySelector('.mobile-menu');

hamburger?.addEventListener('click', () => {
  const open = hamburger.classList.toggle('open');
  mobileMenu?.classList.toggle('open', open);
  document.body.style.overflow = open ? 'hidden' : '';
});

// Mobile sub-menus
document.querySelectorAll('.mobile-nav-link[data-sub]').forEach(link => {
  link.addEventListener('click', () => {
    const subId = link.dataset.sub;
    const sub   = document.getElementById(subId);
    if (!sub) return;
    const isOpen = sub.classList.toggle('open');
    const chevron = link.querySelector('.m-chevron');
    if (chevron) chevron.style.transform = isOpen ? 'rotate(180deg)' : '';
  });
});

// Close on outside click
document.addEventListener('click', e => {
  if (mobileMenu?.classList.contains('open') &&
      !mobileMenu.contains(e.target) &&
      !hamburger.contains(e.target)) {
    hamburger.classList.remove('open');
    mobileMenu.classList.remove('open');
    document.body.style.overflow = '';
  }
});

// ── Scroll animations (IntersectionObserver) ─────────────────
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.08, rootMargin: '0px 0px -20px 0px' });

document.querySelectorAll('[data-animate]').forEach(el => observer.observe(el));

// Fire immediately for elements already in viewport on load
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    document.querySelectorAll('[data-animate]').forEach(el => {
      const rect = el.getBoundingClientRect();
      if (rect.top < window.innerHeight && rect.bottom > 0) {
        el.classList.add('visible');
      }
    });
  });
});

// ── Verse Carousel ───────────────────────────────────────────
const verses = [
  {
    text: "Proclamez l'Évangile du Royaume dans le monde entier, pour servir de témoignage à toutes les nations. Alors viendra la fin.",
    ref:  "Matthieu 24:14"
  },
  {
    text: "Car Dieu a tant aimé le monde qu'il a donné son Fils unique, afin que quiconque croit en lui ne périsse point, mais qu'il ait la vie éternelle.",
    ref:  "Jean 3:16"
  },
  {
    text: "Sortez du milieu d'elle, mon peuple, afin que vous ne participiez point à ses péchés, et que vous n'ayez point de part à ses fléaux.",
    ref:  "Apocalypse 18:4"
  },
  {
    text: "Cherchez le Seigneur pendant qu'il se trouve ; invoquez-le tandis qu'il est proche.",
    ref:  "Ésaïe 55:6"
  },
  {
    text: "Car la grâce de Dieu, source de salut pour tous les hommes, a été manifestée.",
    ref:  "Tite 2:11"
  }
];

let currentVerse = 0;
const verseText  = document.querySelector('.verse-text');
const verseRef   = document.querySelector('.verse-ref span');
const verseDots  = document.querySelectorAll('.verse-dot');

function showVerse(idx) {
  if (!verseText || !verseRef) return;
  verseText.style.opacity = '0';
  verseText.style.transform = 'translateY(10px)';
  setTimeout(() => {
    verseText.textContent = verses[idx].text;
    verseRef.textContent  = verses[idx].ref;
    verseText.style.transition = 'opacity .5s ease, transform .5s ease';
    verseText.style.opacity = '1';
    verseText.style.transform = 'translateY(0)';
    verseDots.forEach((d, i) => d.classList.toggle('active', i === idx));
  }, 300);
  currentVerse = idx;
}

document.querySelector('.verse-prev')?.addEventListener('click', () => {
  showVerse((currentVerse - 1 + verses.length) % verses.length);
});
document.querySelector('.verse-next')?.addEventListener('click', () => {
  showVerse((currentVerse + 1) % verses.length);
});
verseDots.forEach((dot, i) => dot.addEventListener('click', () => showVerse(i)));

// Auto-advance every 7s (uniquement si le carousel est présent sur la page)
const verseCarousel = document.querySelector('.verse-carousel');
let verseTimer = verseCarousel
  ? setInterval(() => { showVerse((currentVerse + 1) % verses.length); }, 7000)
  : null;

verseCarousel?.addEventListener('mouseenter', () => clearInterval(verseTimer));
verseCarousel?.addEventListener('mouseleave', () => {
  verseTimer = setInterval(() => showVerse((currentVerse + 1) % verses.length), 7000);
});

// ── Progress bars animation ──────────────────────────────────
const progressObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const bar = entry.target;
      bar.style.width = bar.dataset.width;
      progressObserver.unobserve(bar);
    }
  });
}, { threshold: 0.5 });

document.querySelectorAll('.progress-bar').forEach(bar => {
  bar.style.width = '0%';
  progressObserver.observe(bar);
});


// ── Smooth scroll for anchor links ──────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', e => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) {
      e.preventDefault();
      const offset = header ? header.offsetHeight + 24 : 0;
      window.scrollTo({ top: target.offsetTop - offset, behavior: 'smooth' });
      // Close mobile menu if open
      hamburger?.classList.remove('open');
      mobileMenu?.classList.remove('open');
      document.body.style.overflow = '';
    }
  });
});

// ── Counter animation ────────────────────────────────────────
function animateCounter(el) {
  const target = parseInt(el.dataset.count, 10);
  const duration = 1800;
  const step = target / (duration / 16);
  let current = 0;
  const timer = setInterval(() => {
    current = Math.min(current + step, target);
    el.textContent = Math.floor(current).toLocaleString('fr-FR') + (el.dataset.suffix || '');
    if (current >= target) clearInterval(timer);
  }, 16);
}

const counterObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      animateCounter(entry.target);
      counterObserver.unobserve(entry.target);
    }
  });
}, { threshold: 0.7 });

document.querySelectorAll('[data-count]').forEach(el => counterObserver.observe(el));
