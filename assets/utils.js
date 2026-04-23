// TLTJB shared utilities
// Loaded on every page before page-specific scripts

let DATA = null;

async function loadData() {
  if (DATA) return DATA;
  const r = await fetch('data/data.json');
  DATA = await r.json();
  return DATA;
}

function fmt(n, dec = 2) {
  if (n == null || isNaN(n)) return '—';
  return Number(n).toFixed(dec);
}
function fmtPct(n) {
  if (n == null || isNaN(n)) return '—';
  return (Number(n) * 100).toFixed(1) + '%';
}
function fmtRecord(w, l) { return `${w}-${l}`; }

function typeLabel(type, round) {
  if (type === 'regular') return '<span class="badge badge-regular">REG</span>';
  if (round === 'Championship') return '<span class="badge badge-championship">CHAMP</span>';
  if (round === 'Semis') return '<span class="badge badge-semis">SEMIS</span>';
  if (round === 'Quarters') return '<span class="badge badge-quarters">QTR</span>';
  if (round === '3rd Place') return '<span class="badge badge-playoffs">3RD</span>';
  return '<span class="badge badge-playoffs">PO</span>';
}

function sortTable(table, colIdx, numericCols = []) {
  const th = table.querySelectorAll('thead th')[colIdx];
  const asc = th.classList.contains('sorted-asc');
  table.querySelectorAll('thead th').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
  th.classList.add(asc ? 'sorted-desc' : 'sorted-asc');
  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const numeric = numericCols.includes(colIdx);
  rows.sort((a, b) => {
    const av = a.cells[colIdx]?.textContent.trim().replace(/[^0-9.\-]/g, '') || '';
    const bv = b.cells[colIdx]?.textContent.trim().replace(/[^0-9.\-]/g, '') || '';
    const cmp = numeric ? (parseFloat(av) || 0) - (parseFloat(bv) || 0)
                        : av.localeCompare(bv, undefined, { numeric: true });
    return asc ? -cmp : cmp;
  });
  rows.forEach(r => tbody.appendChild(r));
}

function initSortableTables() {
  document.querySelectorAll('table[data-sortable]').forEach(table => {
    const numericCols = (table.dataset.numericCols || '').split(',').map(Number).filter(n => !isNaN(n));
    table.querySelectorAll('thead th').forEach((th, i) => {
      th.addEventListener('click', () => sortTable(table, i, numericCols));
    });
  });
}

function setActiveNav() {
  const path = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach(a => {
    const href = a.getAttribute('href');
    if (href === path || (path === '' && href === 'index.html')) {
      a.classList.add('active');
    }
  });
}

function initHamburger() {
  const btn = document.querySelector('.hamburger');
  const menu = document.querySelector('.mobile-menu');
  if (!btn || !menu) return;
  btn.addEventListener('click', () => menu.classList.toggle('open'));
  menu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => menu.classList.remove('open')));
}

document.addEventListener('DOMContentLoaded', () => {
  setActiveNav();
  initHamburger();
});
