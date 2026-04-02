/**
 * admin_darkmode.js
 * 1. ライトモード強制（ダークモード無効）
 * 2. サイドバーグループの開閉状態をlocalStorageに保持
 * 3. サイドバースクロール位置の保持
 */
(function () {
  'use strict';

  // =============================================
  // Force Light Mode (dark mode completely disabled)
  // =============================================
  // 1. Jazzmin/Bootstrap theme attribute
  document.documentElement.setAttribute('data-bs-theme', 'light');
  document.documentElement.removeAttribute('data-theme');
  localStorage.removeItem('jazzmin-theme-mode');

  // 2. Prevent browser from applying dark color scheme
  document.documentElement.style.colorScheme = 'light only';

  // 3. Inject meta tag to block prefers-color-scheme: dark
  if (!document.querySelector('meta[name="color-scheme"]')) {
    var meta = document.createElement('meta');
    meta.name = 'color-scheme';
    meta.content = 'light only';
    document.head.appendChild(meta);
  }

  // 4. Remove dark mode toggle button if present
  function removeDarkToggle() {
    var toggle = document.querySelector('.theme-toggle, #dark-mode-toggle, [data-theme-toggle]');
    if (toggle) toggle.remove();
  }

  // =============================================
  // Sidebar Scroll Position Persistence
  // =============================================

  var SCROLL_KEY = 'sidebar-scroll-top';

  function saveSidebarScroll() {
    var sidebar = document.querySelector('.main-sidebar .sidebar, #jazzy-sidebar');
    if (sidebar) {
      sessionStorage.setItem(SCROLL_KEY, sidebar.scrollTop);
    }
  }

  function restoreSidebarScroll() {
    var sidebar = document.querySelector('.main-sidebar .sidebar, #jazzy-sidebar');
    if (!sidebar) return;
    var saved = sessionStorage.getItem(SCROLL_KEY);
    if (saved) {
      sidebar.scrollTop = parseInt(saved, 10);
    }
  }

  function setupScrollPersistence() {
    document.querySelectorAll('.main-sidebar a, #jazzy-sidebar a').forEach(function(link) {
      link.addEventListener('click', saveSidebarScroll);
    });
    window.addEventListener('beforeunload', saveSidebarScroll);
    restoreSidebarScroll();
  }

  // =============================================
  // Sidebar Group Open State Persistence
  // =============================================

  var STORAGE_KEY = 'sidebar-open-groups';

  function getSavedGroups() {
    try {
      var data = localStorage.getItem(STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      return [];
    }
  }

  function saveOpenGroups() {
    var open = [];
    document.querySelectorAll('#jazzy-sidebar .nav-item.has-treeview.menu-open').forEach(function (el) {
      var link = el.querySelector(':scope > .nav-link');
      if (link) {
        var text = link.textContent.trim();
        if (text) open.push(text);
      }
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(open));
  }

  function restoreOpenGroups() {
    var saved = getSavedGroups();
    if (!saved.length) return;

    document.querySelectorAll('#jazzy-sidebar .nav-item.has-treeview').forEach(function (el) {
      var link = el.querySelector(':scope > .nav-link');
      if (!link) return;
      var text = link.textContent.trim();
      if (saved.indexOf(text) !== -1) {
        el.classList.add('menu-is-opening', 'menu-open');
        var sub = el.querySelector('.nav-treeview');
        if (sub) sub.style.display = 'block';
      }
    });
  }

  function setupSidebarPersistence() {
    document.querySelectorAll('#jazzy-sidebar .nav-item.has-treeview > .nav-link').forEach(function (link) {
      link.addEventListener('click', function () {
        setTimeout(saveOpenGroups, 100);
      });
    });

    var activeLink = document.querySelector('#jazzy-sidebar a.nav-link.active');
    if (activeLink) {
      var parentGroup = activeLink.closest('.nav-item.has-treeview');
      if (parentGroup) {
        parentGroup.classList.add('menu-is-opening', 'menu-open');
        var sub = parentGroup.querySelector('.nav-treeview');
        if (sub) sub.style.display = 'block';
        setTimeout(saveOpenGroups, 200);
      }
    }

    restoreOpenGroups();
  }

  // =============================================
  // Init
  // =============================================

  function init() {
    removeDarkToggle();
    setupSidebarPersistence();
    setupScrollPersistence();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

// =============================================
// Load additional admin modules
// =============================================
(function () {
  'use strict';
  var EXTRA_SCRIPTS = ['/static/js/admin_marquee.js'];
  EXTRA_SCRIPTS.forEach(function (src) {
    var s = document.createElement('script');
    s.src = src;
    s.defer = true;
    document.head.appendChild(s);
  });
})();
