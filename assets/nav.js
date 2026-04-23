// nav.js - injects navbar and footer into every page
(function () {
  const NAV_HTML = `
<nav class="navbar">
  <div class="nav-inner">
    <a class="nav-brand" href="index.html">
      <img src="assets/images/logo.png" alt="TLTJB">
      <span>TLTJB</span>
    </a>
    <ul class="nav-links">
      <li><a href="index.html">Home</a></li>
      <li><a href="seasons.html">Seasons</a></li>
      <li><a href="owners.html">Owners</a></li>
      <li><a href="head-to-head.html">Head to Head</a></li>
      <li><a href="playoffs.html">Playoffs</a></li>
      <li><a href="records.html">Records</a></li>
    </ul>
    <button class="hamburger" aria-label="Menu">
      <span></span><span></span><span></span>
    </button>
  </div>
  <div class="mobile-menu">
    <a href="index.html">🏠 Home</a>
    <a href="seasons.html">📅 Seasons</a>
    <a href="owners.html">👤 Owners</a>
    <a href="head-to-head.html">⚔️ Head to Head</a>
    <a href="playoffs.html">🏆 Playoffs</a>
    <a href="records.html">📊 Records</a>
  </div>
</nav>`;

  const FOOTER_HTML = `
<footer>
  <p>The League That Johnny Built &nbsp;|&nbsp; Est. 2013 &nbsp;|&nbsp; Powered by ESPN</p>
  <p style="margin-top:0.3rem;" id="footer-updated"></p>
</footer>`;

  document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    body.insertAdjacentHTML('afterbegin', NAV_HTML);
    body.insertAdjacentHTML('beforeend', FOOTER_HTML);
    const upd = document.getElementById('footer-updated');
    if (upd) upd.textContent = `Last updated: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`;
  });
})();
