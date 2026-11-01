// Progressive enhancement: the page works without JS; this adds search + collection filtering.
const search = document.querySelector('#search');
const chips = [...document.querySelectorAll('.chip')];
const cards = [...document.querySelectorAll('.card')];
const sections = [...document.querySelectorAll('.collection')];
const empty = document.querySelector('#empty');
let active = 'all';

function apply() {
  const q = search.value.trim().toLowerCase();
  let shown = 0;
  for (const card of cards) {
    const inCollection = active === 'all' || card.dataset.collection === active;
    const matches = !q || card.dataset.search.includes(q);
    card.hidden = !(inCollection && matches);
    if (!card.hidden) shown++;
  }
  for (const s of sections) s.hidden = !s.querySelector('.card:not([hidden])');
  empty.hidden = shown > 0;
}

search.addEventListener('input', apply);
for (const chip of chips) {
  chip.addEventListener('click', () => {
    active = chip.dataset.filter;
    chips.forEach(c => c.setAttribute('aria-pressed', String(c === chip)));
    apply();
  });
}

