/**
 * admin_darkmode.js
 * 1. Dark/Light モード切替ボタン（navbar）
 * 2. サイドバーグループの開閉状態をlocalStorageに保持
 */
(function () {
  'use strict';

  // =============================================
  // Dark Mode Toggle
  // =============================================

  // ページロード直後にlocalStorageからテーマを復元（FOUC防止）
  var savedMode = localStorage.getItem('jazzmin-theme-mode');
  if (savedMode === 'dark' || savedMode === 'light') {
    document.documentElement.setAttribute('data-bs-theme', savedMode);
  }

  function getCurrentMode() {
    return document.documentElement.getAttribute('data-bs-theme') || 'light';
  }

  function setMode(mode) {
    document.documentElement.setAttribute('data-bs-theme', mode);
    localStorage.setItem('jazzmin-theme-mode', mode);
    // サイドバーのダーク切替
    var sidebar = document.querySelector('.main-sidebar');
    if (sidebar) {
      if (mode === 'dark') {
        sidebar.classList.remove('sidebar-dark-indigo');
        sidebar.classList.add('sidebar-dark-primary');
      } else {
        sidebar.classList.remove('sidebar-dark-primary');
        sidebar.classList.add('sidebar-dark-indigo');
      }
    }
    updateIcon(mode);
  }

  function updateIcon(mode) {
    var btn = document.getElementById('darkmode-toggle');
    if (!btn) return;
    var icon = btn.querySelector('i');
    if (!icon) return;
    if (mode === 'dark') {
      icon.className = 'fas fa-sun';
      btn.title = 'ライトモード';
    } else {
      icon.className = 'fas fa-moon';
      btn.title = 'ナイトモード';
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
    btn.style.cssText = 'font-size:1.1rem;padding:0.5rem 0.75rem;cursor:pointer;';

    var icon = document.createElement('i');
    btn.appendChild(icon);
    li.appendChild(btn);

    navbar.insertBefore(li, navbar.firstChild);
    updateIcon(getCurrentMode());

    btn.addEventListener('click', function (e) {
      e.preventDefault();
      var current = getCurrentMode();
      setMode(current === 'dark' ? 'light' : 'dark');
    });
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
    // Save scroll on any link click (before navigation)
    document.querySelectorAll('.main-sidebar a, #jazzy-sidebar a').forEach(function(link) {
      link.addEventListener('click', saveSidebarScroll);
    });
    // Also save on beforeunload for any navigation
    window.addEventListener('beforeunload', saveSidebarScroll);
    // Restore on page load
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
    // グループヘッダーのクリックを監視して開閉状態を保存
    document.querySelectorAll('#jazzy-sidebar .nav-item.has-treeview > .nav-link').forEach(function (link) {
      link.addEventListener('click', function () {
        // AdminLTEのトグル処理が終わるのを待ってから保存
        setTimeout(saveOpenGroups, 100);
      });
    });

    // 現在のページのアクティブなグループも自動で開く
    var activeLink = document.querySelector('#jazzy-sidebar a.nav-link.active');
    if (activeLink) {
      var parentGroup = activeLink.closest('.nav-item.has-treeview');
      if (parentGroup) {
        parentGroup.classList.add('menu-is-opening', 'menu-open');
        var sub = parentGroup.querySelector('.nav-treeview');
        if (sub) sub.style.display = 'block';
        // アクティブなグループも保存対象に追加
        setTimeout(saveOpenGroups, 200);
      }
    }

    // 保存済みグループを復元
    restoreOpenGroups();
  }

  // =============================================
  // Init
  // =============================================

  function init() {
    injectToggle();
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
  // Load shared dark mode CSS
  var link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = '/static/css/admin_darkmode.css';
  document.head.appendChild(link);
})();
