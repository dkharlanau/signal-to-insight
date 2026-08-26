const searchInput = document.getElementById('librarySearch');
const cards = [...document.querySelectorAll('.library-card')];
const filterButtons = [...document.querySelectorAll('.filter-chip')];
const count = document.getElementById('libraryCount');
let activeFilter = 'all';

function applyLibraryFilters() {
  const query = (searchInput?.value || '').trim().toLowerCase();
  let visible = 0;

  cards.forEach((card) => {
    const searchable = card.dataset.search || '';
    const tags = (card.dataset.tags || '').split(/\s+/).filter(Boolean);
    const queryMatches = !query || searchable.includes(query);
    const filterMatches = activeFilter === 'all' || tags.includes(activeFilter);
    const show = queryMatches && filterMatches;
    card.hidden = !show;
    if (show) visible += 1;
  });

  if (count) count.textContent = `${visible} explainer${visible === 1 ? '' : 's'}`;
}

searchInput?.addEventListener('input', applyLibraryFilters);
filterButtons.forEach((button) => {
  button.addEventListener('click', () => {
    activeFilter = button.dataset.filter || 'all';
    filterButtons.forEach((candidate) => candidate.classList.toggle('is-active', candidate === button));
    applyLibraryFilters();
  });
});

applyLibraryFilters();