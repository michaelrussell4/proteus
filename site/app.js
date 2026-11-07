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
const downloadVisibleBtn = document.getElementById('btn-download-visible');
const downloadVisibleLabel = document.getElementById('btn-download-visible-label');
const downloadAllHeroBtn = document.getElementById('btn-download-all-hero');

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
  if (downloadVisibleBtn && downloadVisibleLabel && !downloadVisibleBtn.disabled) {
    downloadVisibleBtn.hidden = visibleCount === 0;
    if (visibleCount === catalog.length) {
      downloadVisibleLabel.textContent = `Download All (${visibleCount} EPUBs)`;
    } else {
      downloadVisibleLabel.textContent = `Download Shown (${visibleCount} ${visibleCount === 1 ? 'EPUB' : 'EPUBs'})`;
    }
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

/**
 * Download All / Download Shown EPUBs as a Single Uncompressed (STORE) ZIP Archive
 * Since .epub files are already DEFLATE-compressed archives, storing them directly
 * in a standard ZIP container requires zero CPU compression overhead and avoids
 * browser multiple-file download blocking.
 */
const CRC32_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    }
    table[i] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < bytes.length; i++) {
    crc = CRC32_TABLE[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function buildStoreZip(files) {
  const encoder = new TextEncoder();
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  for (const { name, data } of files) {
    const nameBytes = encoder.encode(name);
    const crc = crc32(data);
    const size = data.byteLength;

    // Local file header (30 bytes + filename)
    const localHeader = new Uint8Array(30 + nameBytes.length);
    const lv = new DataView(localHeader.buffer);
    lv.setUint32(0, 0x04034b50, true); // Local file header signature
    lv.setUint16(4, 20, true);         // Version needed to extract (2.0)
    lv.setUint16(6, 0x0800, true);     // UTF-8 filename flag
    lv.setUint16(8, 0, true);          // Compression method: 0 (STORE)
    lv.setUint16(10, 0, true);         // Mod time
    lv.setUint16(12, 0, true);         // Mod date
    lv.setUint32(14, crc, true);       // CRC-32
    lv.setUint32(18, size, true);      // Compressed size
    lv.setUint32(22, size, true);      // Uncompressed size
    lv.setUint16(26, nameBytes.length, true);
    lv.setUint16(28, 0, true);         // Extra field length
    localHeader.set(nameBytes, 30);

    localParts.push(localHeader, data);

    // Central directory header (46 bytes + filename)
    const centralHeader = new Uint8Array(46 + nameBytes.length);
    const cv = new DataView(centralHeader.buffer);
    cv.setUint32(0, 0x02014b50, true); // Central directory signature
    cv.setUint16(4, 20, true);         // Version made by
    cv.setUint16(6, 20, true);         // Version needed
    cv.setUint16(8, 0x0800, true);     // UTF-8 flag
    cv.setUint16(10, 0, true);         // Compression: STORE
    cv.setUint16(12, 0, true);
    cv.setUint16(14, 0, true);
    cv.setUint32(16, crc, true);
    cv.setUint32(20, size, true);
    cv.setUint32(24, size, true);
    cv.setUint16(28, nameBytes.length, true);
    cv.setUint16(30, 0, true);
    cv.setUint16(32, 0, true);
    cv.setUint16(34, 0, true);
    cv.setUint16(36, 0, true);
    cv.setUint32(38, 0, true);
    cv.setUint32(42, offset, true);    // Relative offset of local header
    centralHeader.set(nameBytes, 46);

    centralParts.push(centralHeader);
    offset += localHeader.byteLength + size;
  }

  const centralSize = centralParts.reduce((acc, p) => acc + p.byteLength, 0);
  const eocd = new Uint8Array(22);
  const ev = new DataView(eocd.buffer);
  ev.setUint32(0, 0x06054b50, true);   // End of central directory signature
  ev.setUint16(4, 0, true);
  ev.setUint16(6, 0, true);
  ev.setUint16(8, files.length, true);
  ev.setUint16(10, files.length, true);
  ev.setUint32(12, centralSize, true);
  ev.setUint32(16, offset, true);
  ev.setUint16(20, 0, true);

  return new Blob([...localParts, ...centralParts, eocd], { type: 'application/zip' });
}

let isBatchDownloading = false;

async function handleDownloadAll(mode, triggerBtn) {
  if (isBatchDownloading) return;

  let targetBooks = catalog;
  let zipName = 'proteus-scriptorium-all-editions.zip';

  if (mode === 'visible') {
    const visibleIds = new Set(
      bookCards.filter(c => !c.hidden).map(c => c.dataset.id)
    );
    targetBooks = catalog.filter(b => visibleIds.has(b.id));
    if (activeFilter !== 'all') {
      zipName = `proteus-scriptorium-${activeFilter}.zip`;
    }
  }

  if (targetBooks.length === 0) return;

  isBatchDownloading = true;
  const labelSpan = triggerBtn.querySelector('span') || triggerBtn;
  const originalText = labelSpan.textContent;
  if (downloadAllHeroBtn) downloadAllHeroBtn.disabled = true;
  if (downloadVisibleBtn) downloadVisibleBtn.disabled = true;

  try {
    const fetchedFiles = new Array(targetBooks.length);
    let completed = 0;
    let nextIdx = 0;

    labelSpan.textContent = `Downloading 0 / ${targetBooks.length} EPUBs…`;

    const concurrency = Math.min(4, targetBooks.length);
    async function worker() {
      while (nextIdx < targetBooks.length) {
        const i = nextIdx++;
        const book = targetBooks[i];
        const resp = await fetch(book.file);
        if (!resp.ok) {
          throw new Error(`Failed to fetch ${book.slug}.epub (${resp.status})`);
        }
        const buf = await resp.arrayBuffer();
        fetchedFiles[i] = {
          name: `${book.slug}.epub`,
          data: new Uint8Array(buf),
        };
        completed++;
        labelSpan.textContent = `Downloading ${completed} / ${targetBooks.length} EPUBs…`;
      }
    }

    await Promise.all(Array.from({ length: concurrency }, () => worker()));

    labelSpan.textContent = `Packaging ZIP (${targetBooks.length} EPUBs)…`;
    const zipBlob = buildStoreZip(fetchedFiles);
    const blobUrl = URL.createObjectURL(zipBlob);
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = zipName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 15000);

    labelSpan.textContent = `✓ Downloaded ${targetBooks.length} EPUBs!`;
    setTimeout(() => {
      labelSpan.textContent = originalText;
      updateCatalog();
    }, 3000);
  } catch (err) {
    console.error(err);
    labelSpan.textContent = 'Download failed — click to retry';
    setTimeout(() => {
      labelSpan.textContent = originalText;
      updateCatalog();
    }, 3500);
  } finally {
    isBatchDownloading = false;
    if (downloadAllHeroBtn) downloadAllHeroBtn.disabled = false;
    if (downloadVisibleBtn) downloadVisibleBtn.disabled = false;
  }
}

document.addEventListener('click', (e) => {
  const dlBtn = e.target.closest('[data-download-all]');
  if (dlBtn) {
    handleDownloadAll(dlBtn.getAttribute('data-download-all'), dlBtn);
  }
});

