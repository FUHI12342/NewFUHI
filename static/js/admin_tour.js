/**
 * Admin Tour (Help) — reusable tour engine.
 *
 * Each page sets:
 *   window.TOUR_STEPS       = [ { selector, title, text, action? }, ... ]
 *   window.TOUR_STORAGE_KEY = 'page_name_tour_seen'
 *   window.TOUR_AUTO_START  = true/false (optional, default true)
 */
(function () {
  'use strict';

  var tourCurrentStep = 0;
  var tourOverlay = null;
  var tourTooltip = null;
  var tourPrevHighlight = null;

  function steps() { return window.TOUR_STEPS || []; }
  function storageKey() { return window.TOUR_STORAGE_KEY || 'admin_tour_seen'; }

  function createOverlay() {
    if (tourOverlay) return;
    tourOverlay = document.createElement('div');
    tourOverlay.className = 'tour-overlay';
    tourOverlay.style.display = 'none';
    tourOverlay.onclick = function (e) { if (e.target === tourOverlay) endTour(); };
    document.body.appendChild(tourOverlay);

    tourTooltip = document.createElement('div');
    tourTooltip.className = 'tour-tooltip';
    tourTooltip.style.display = 'none';
    document.body.appendChild(tourTooltip);
  }

  function positionTooltip(el) {
    var rect = el.getBoundingClientRect();
    var tt = tourTooltip;
    var ttW = 340, ttH = tt.offsetHeight || 200;
    var top, left;
    if (rect.bottom + ttH + 16 < window.innerHeight) {
      top = rect.bottom + 12;
    } else {
      top = Math.max(8, rect.top - ttH - 12);
    }
    left = Math.max(8, Math.min(rect.left, window.innerWidth - ttW - 16));
    tt.style.top = top + 'px';
    tt.style.left = left + 'px';
  }

  /** 有効なステップのみをフィルタして返す */
  function getVisibleSteps() {
    var allSteps = steps();
    var visible = [];
    for (var i = 0; i < allSteps.length; i++) {
      var el = document.querySelector(allSteps[i].selector);
      if (el && (el.offsetParent !== null || el.style.position === 'fixed')) {
        visible.push(allSteps[i]);
      }
    }
    return visible;
  }

  function showStep(idx) {
    var visibleSteps = getVisibleSteps();
    if (idx < 0 || idx >= visibleSteps.length) { endTour(); return; }
    tourCurrentStep = idx;
    var step = visibleSteps[idx];

    if (tourPrevHighlight) tourPrevHighlight.classList.remove('tour-highlight');

    // Run action first (e.g. switch tab), then wait for DOM to update
    if (step.action) step.action();

    function doShow() {
      var el = document.querySelector(step.selector);
      if (!el) { endTour(); return; }

      el.classList.add('tour-highlight');
      tourPrevHighlight = el;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });

      tourTooltip.innerHTML =
        '<h4>' + step.title + '</h4><p>' + step.text + '</p>' +
        '<div class="tour-tooltip-footer">' +
          '<span class="tour-step-info">' + (idx + 1) + ' / ' + visibleSteps.length + '</span>' +
          '<div class="tour-btns">' +
            '<button class="tour-btn tour-btn-skip" onclick="endTour()">閉じる</button>' +
            (idx > 0 ? '<button class="tour-btn tour-btn-skip" onclick="window._tourShowStep(' + (idx - 1) + ')">戻る</button>' : '') +
            '<button class="tour-btn tour-btn-next" onclick="window._tourShowStep(' + (idx + 1) + ')">' +
              (idx === visibleSteps.length - 1 ? '完了' : '次へ') +
            '</button>' +
          '</div>' +
        '</div>';
      tourTooltip.style.display = 'block';
      tourOverlay.style.display = 'block';

      setTimeout(function () { positionTooltip(el); }, 150);
    }

    // Delay to allow DOM updates from action (tab switch, etc.)
    if (step.action) {
      setTimeout(doShow, 200);
    } else {
      doShow();
    }
  }

  function startTour() {
    var visibleSteps = getVisibleSteps();
    if (!visibleSteps.length) return;
    createOverlay();
    tourCurrentStep = 0;
    showStep(0);
  }

  function endTour() {
    if (tourPrevHighlight) tourPrevHighlight.classList.remove('tour-highlight');
    if (tourOverlay) tourOverlay.style.display = 'none';
    if (tourTooltip) tourTooltip.style.display = 'none';
    try { localStorage.setItem(storageKey(), '1'); } catch (e) {}
  }

  // Expose globally
  window.startTour = startTour;
  window.endTour = endTour;
  window._tourShowStep = showStep;

  // Auto-show on first visit (after 800ms) — respects TOUR_AUTO_START setting
  document.addEventListener('DOMContentLoaded', function () {
    // TOUR_AUTO_START が明示的に false の場合は自動表示しない
    if (window.TOUR_AUTO_START === false) return;
    try {
      if (!localStorage.getItem(storageKey()) && steps().length) {
        setTimeout(startTour, 800);
      }
    } catch (e) {}
  });
})();
