/**
 * admin_darkmode.js
 * Jazzmin navbar: dark / light mode toggle button
 * Uses the same localStorage key "jazzmin-theme-mode" that Jazzmin reads on page load.
 */
(function () {
  'use strict';

  function getCurrentMode() {
    return document.documentElement.getAttribute('data-bs-theme') || 'light';
  }

  function setMode(mode) {
    document.documentElement.setAttribute('data-bs-theme', mode);
    localStorage.setItem('jazzmin-theme-mode', mode);
    updateIcon(mode);
  }

  function updateIcon(mode) {
    var btn = document.getElementById('darkmode-toggle');
    if (!btn) return;
    var icon = btn.querySelector('i');
    if (!icon) return;
    if (mode === 'dark') {
      icon.className = 'fas fa-sun';
      btn.title = 'Light mode';
    } else {
      icon.className = 'fas fa-moon';
      btn.title = 'Night mode';
    }
  }

  function injectToggle() {
    var navbar = document.querySelector('#jazzy-navbar .navbar-nav.ms-auto');
    if (!navbar) return;

    var li = document.createElement('li');
    li.className = 'nav-item';

    var btn = document.createElement('a');
    btn.id = 'darkmode-toggle';
    btn.className = 'nav-link btn';
    btn.href = '#';
    btn.setAttribute('role', 'button');
    btn.style.cssText = 'font-size:1.1rem;padding:0.5rem 0.75rem;';

    var icon = document.createElement('i');
    btn.appendChild(icon);
    li.appendChild(btn);

    // Insert as first item in the right-side nav
    navbar.insertBefore(li, navbar.firstChild);

    updateIcon(getCurrentMode());

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var current = getCurrentMode();
      setMode(current === 'dark' ? 'light' : 'dark');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectToggle);
  } else {
    injectToggle();
  }
})();
