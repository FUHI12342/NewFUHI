/**
 * サイドバーメニュー開閉維持
 *
 * 子メニュークリック→ページ遷移後も、親メニューグループを開いた状態に保つ。
 * 1. 現在のURLパスに一致するサイドバーリンクの親グループを自動展開
 * 2. sessionStorage で最後に開いたグループを記憶（URL一致がない場合のフォールバック）
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'sidebar_open_indices';

  function getSaved() {
    try {
      return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || [];
    } catch (e) {
      return [];
    }
  }

  function save(indices) {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(indices));
    } catch (e) { /* ignore */ }
  }

  function openGroup(item) {
    item.classList.add('menu-open', 'menu-is-opening');
    var sub = item.querySelector('.nav-treeview');
    if (sub) sub.style.display = 'block';
  }

  function init() {
    var path = window.location.pathname;
    var treeItems = document.querySelectorAll(
      '#jazzy-navigation > .nav-item.has-treeview'
    );
    if (!treeItems.length) return;

    var matchedIndices = [];

    // Pass 1: 現在URLに一致するリンクの親グループを展開
    treeItems.forEach(function (item, idx) {
      var links = item.querySelectorAll('.nav-treeview .nav-link');
      var isMatch = false;
      links.forEach(function (a) {
        var href = a.getAttribute('href');
        if (!href || href === '#' || href === 'javascript:void(0)') return;
        // クエリ文字列を除去して比較
        var hrefPath = href.split('?')[0].replace(/\/+$/, '');
        var curPath = path.replace(/\/+$/, '');
        if (curPath === hrefPath || curPath.indexOf(hrefPath + '/') === 0) {
          isMatch = true;
          a.classList.add('active');
        }
      });
      if (isMatch) {
        openGroup(item);
        matchedIndices.push(idx);
      }
    });

    // URL一致があれば sessionStorage に保存
    if (matchedIndices.length > 0) {
      save(matchedIndices);
    } else {
      // Pass 2: URL一致なし → sessionStorage からフォールバック
      var saved = getSaved();
      saved.forEach(function (idx) {
        if (idx < treeItems.length) {
          openGroup(treeItems[idx]);
        }
      });
    }

    // 手動開閉を監視して sessionStorage に保存
    treeItems.forEach(function (item) {
      var toggle = item.querySelector(':scope > .nav-link');
      if (!toggle) return;
      toggle.addEventListener('click', function () {
        // AdminLTE がクラスを切り替えた後に保存
        setTimeout(function () {
          var open = [];
          treeItems.forEach(function (ti, i) {
            if (ti.classList.contains('menu-open')) open.push(i);
          });
          save(open);
        }, 100);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
