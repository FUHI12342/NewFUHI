/**
 * Store change form: タブ内に保存ボタン配置 + サイトカスタマイズをタブ化
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var tabBar = document.querySelector('.nav.nav-tabs, #jazzy-tabs, ul.changeform-tabs');
    var tabContent = document.querySelector('.tab-content');
    if (!tabBar || !tabContent) return;

    // --- 1. サイトカスタマイズ fieldset をタブに統合 ---
    var custFieldset = null;
    document.querySelectorAll('fieldset.module h2').forEach(function (h2) {
      if (h2.textContent.trim() === 'サイトカスタマイズ') {
        custFieldset = h2.closest('fieldset');
      }
    });

    if (custFieldset) {
      // タブヘッダー追加
      var tabId = 'tab-site-customize';
      var li = document.createElement('li');
      li.className = 'nav-item';
      li.innerHTML = '<a class="nav-link" href="#' + tabId + '" data-toggle="tab" data-bs-toggle="tab" role="tab">サイトカスタマイズ</a>';
      tabBar.appendChild(li);

      // タブパネル作成
      var pane = document.createElement('div');
      pane.className = 'tab-pane';
      pane.id = tabId;
      pane.setAttribute('role', 'tabpanel');
      pane.appendChild(custFieldset);
      tabContent.appendChild(pane);
    }

    // --- 2. 各タブパネルの右下に保存ボタンを配置 ---
    var submitRow = document.querySelector('.submit-row');
    if (!submitRow) return;

    var panes = tabContent.querySelectorAll('.tab-pane');
    panes.forEach(function (pane) {
      var clone = submitRow.cloneNode(true);
      clone.classList.add('tab-submit-row');
      clone.style.marginTop = '24px';
      clone.style.display = 'flex';
      clone.style.justifyContent = 'flex-end';
      clone.style.gap = '8px';
      clone.style.borderTop = '1px solid #dee2e6';
      clone.style.paddingTop = '16px';

      // 「削除」ボタンはタブ内には不要 — 非表示
      var delLink = clone.querySelector('.deletelink, .deletelink-box, a[href*="delete"]');
      if (delLink) delLink.style.display = 'none';

      pane.appendChild(clone);
    });

    // 元の submit-row は非表示（二重表示防止）
    submitRow.style.display = 'none';

    // --- 3. インライン内の「削除」リンクを非表示 ---
    document.querySelectorAll('.inline-deletelink, .inline-related .delete a, .inline-related a.inline-deletelink').forEach(function (el) {
      el.style.display = 'none';
    });
    // jazzmin stacked inline の「削除」テキストリンク
    document.querySelectorAll('.inline-related').forEach(function (inline) {
      inline.querySelectorAll('a').forEach(function (a) {
        if (a.textContent.trim() === '削除' || a.textContent.trim() === 'Delete') {
          a.style.display = 'none';
        }
      });
    });
  });
})();
