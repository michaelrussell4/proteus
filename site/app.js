/**
 * Proteus Scriptorium - Client Application
 * Handles instant filtering, sorting, theme toggling, and accessible modal dialog previews.
 */

// Load embedded catalog data
const catalogDataElement = document.getElementById('catalog-data');
const catalog = catalogDataElement ? JSON.parse(catalogDataElement.textContent) : [];
const bookMap = new Map(catalog.map(b => [b.id, b]));

// DOM Elements
const searchInput = document.getElementById('catalog-search');
const searchClearBtn = document.getElementById('search-clear');
const filterChips = Array.from(document.querySelectorAll('.filter-chips .chip'));
const sortSelect = document.getElementById('catalog-sort');
const booksGrid = document.getElementById('books-grid');
const bookCards = Array.from(document.querySelectorAll('.book-card'));
const resultsCount = document.getElementById('results-count');
const emptyState = document.getElementById('empty-state');
const resetFiltersBtn = document.getElementById('reset-filters');
const themeToggleBtn = document.getElementById('theme-toggle');

// Modal Elements
const modal = document.getElementById('book-modal');
const modalCloseBtn = document.getElementById('modal-close');
const modalCover = document.getElementById('modal-book-cover');
const modalBadge = document.getElementById('modal-book-badge');
const modalTitle = document.getElementById('modal-book-title');
const modalSubtitle = document.getElementById('modal-book-subtitle');
const modalCollection = document.getElementById('modal-book-collection');
const modalCreator = document.getElementById('modal-book-creator');
const modalDesc = document.getElementById('modal-book-desc');
const modalHighlights = document.getElementById('modal-book-highlights');
const modalContents = document.getElementById('modal-book-contents');
const modalDownloadBtn = document.getElementById('modal-download-btn');
const modalDownloadText = document.getElementById('modal-download-text');
const modalFileSize = document.getElementById('modal-book-size');

// State
let activeFilter = 'all';
let searchQuery = '';
let currentSort = 'featured';

/**
 * Filter & Sort Logic
 */
function updateCatalog() {
  const query = searchQuery.trim().toLowerCase();
  let visibleCount = 0;

  // Filter visibility
  for (const card of bookCards) {
    const cardCollection = card.dataset.collection;
    const cardSearch = card.dataset.search || '';

    const matchesFilter = activeFilter === 'all' || cardCollection === activeFilter;
    const matchesSearch = !query || cardSearch.includes(query);

    const isVisible = matchesFilter && matchesSearch;
    card.hidden = !isVisible;
    if (isVisible) visibleCount++;
  }

  // Update counts and empty state
  if (resultsCount) {
    resultsCount.innerHTML = `Showing <strong>${visibleCount}</strong> ${visibleCount === 1 ? 'edition' : 'editions'}`;
  }
  if (emptyState) {
    emptyState.hidden = visibleCount > 0;
  }

  // Sorting
  sortCards();
}

function sortCards() {
  if (!booksGrid) return;

  const cardsToSort = Array.from(bookCards);

  cardsToSort.sort((a, b) => {
    const bookA = bookMap.get(a.dataset.id);
    const bookB = bookMap.get(b.dataset.id);

    if (!bookA || !bookB) return 0;

    switch (currentSort) {
      case 'title':
        return bookA.title.localeCompare(bookB.title);
      case 'size-desc':
        return bookB.size_bytes - bookA.size_bytes;
      case 'size-asc':
        return bookA.size_bytes - bookB.size_bytes;
      case 'featured':
      default:
        return catalog.indexOf(bookA) - catalog.indexOf(bookB);
    }
  });

  for (const card of cardsToSort) {
    booksGrid.appendChild(card);
  }
}

// Search input handling
if (searchInput) {
  searchInput.addEventListener('input', (e) => {
    searchQuery = e.target.value;
    if (searchClearBtn) {
      searchClearBtn.hidden = !searchQuery;
    }
    updateCatalog();
  });
}

if (searchClearBtn) {
  searchClearBtn.addEventListener('click', () => {
    searchInput.value = '';
    searchQuery = '';
    searchClearBtn.hidden = true;
    searchInput.focus();
    updateCatalog();
  });
}

// Filter chips handling
for (const chip of filterChips) {
  chip.addEventListener('click', () => {
    activeFilter = chip.dataset.filter;
    for (const c of filterChips) {
      c.setAttribute('aria-pressed', String(c === chip));
    }
    updateCatalog();
  });
}

// Sort dropdown handling
if (sortSelect) {
  sortSelect.addEventListener('change', (e) => {
    currentSort = e.target.value;
    sortCards();
  });
}

// Reset filters button
if (resetFiltersBtn) {
  resetFiltersBtn.addEventListener('click', () => {
    searchQuery = '';
    activeFilter = 'all';
    if (searchInput) searchInput.value = '';
    if (searchClearBtn) searchClearBtn.hidden = true;
    for (const chip of filterChips) {
      chip.setAttribute('aria-pressed', String(chip.dataset.filter === 'all'));
    }
    updateCatalog();
  });
}

/**
 * Modal Dialog Management (<dialog>)
 */
function openBookModal(bookId) {
  const book = bookMap.get(bookId);
  if (!book || !modal) return;

  // Set modal fields
  modalCover.src = book.cover;
  modalCover.alt = `Cover art for ${book.title}`;
  modalBadge.textContent = book.badge || 'Proteus Edition';
  modalTitle.textContent = book.title;
  modalSubtitle.textContent = book.subtitle || '';
  modalCollection.textContent = book.collection_label || '';
  modalCreator.textContent = book.creator ? `By ${book.creator}` : '';
  modalDesc.textContent = book.full_desc || book.short_desc;
  modalContents.textContent = book.contents_summary || '';
  modalFileSize.textContent = `File size: ${book.size_human} (EPUB3)`;

  modalDownloadBtn.href = book.file;
  modalDownloadBtn.setAttribute('download', `${book.slug}.epub`);
  modalDownloadText.textContent = `Download EPUB (${book.size_human})`;

  // Render highlights
  modalHighlights.innerHTML = '';
  if (Array.isArray(book.highlights) && book.highlights.length > 0) {
    for (const item of book.highlights) {
      const li = document.createElement('li');
      li.textContent = item;
      modalHighlights.appendChild(li);
    }
    modalHighlights.parentElement.hidden = false;
  } else {
    modalHighlights.parentElement.hidden = true;
  }

  // Open modal natively
  if (typeof modal.showModal === 'function') {
    modal.showModal();
  }
}

function closeBookModal() {
  if (modal && typeof modal.close === 'function') {
    modal.close();
  }
}

// Event delegation for opening modal
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-open-modal]');
  if (btn) {
    const bookId = btn.getAttribute('data-open-modal');
    openBookModal(bookId);
  }
});

if (modalCloseBtn) {
  modalCloseBtn.addEventListener('click', closeBookModal);
}

// Light dismiss fallback for dialog (per modern web guidance)
if (modal && !('closedBy' in HTMLDialogElement.prototype)) {
  const isOutside = (e, dialog) => {
    const r = dialog.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
  };

  let pressedOutside = false;
  modal.addEventListener('pointerdown', (e) => {
    pressedOutside = isOutside(e, modal);
  });
  modal.addEventListener('pointerup', (e) => {
    if (pressedOutside && isOutside(e, modal)) {
      modal.close();
    }
  });
}

/**
 * Theme Toggle Management
 */
function initTheme() {
  const savedTheme = localStorage.getItem('proteus-theme');
  if (savedTheme) {
    document.documentElement.setAttribute('data-theme', savedTheme);
  }
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  let newTheme;

  if (currentTheme === 'dark') {
    newTheme = 'light';
  } else if (currentTheme === 'light') {
    newTheme = 'dark';
  } else {
    // If not set, check system preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    newTheme = prefersDark ? 'light' : 'dark';
  }

  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('proteus-theme', newTheme);
}

if (themeToggleBtn) {
  themeToggleBtn.addEventListener('click', toggleTheme);
}

initTheme();

