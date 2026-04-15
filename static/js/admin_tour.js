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
  var tourStepList = [];   // ツアー開始時に確定した有効ステップリスト
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
      top = rect.bottom + window.scrollY + 12;
    } else {
      top = Math.max(8, rect.top + window.scrollY - ttH - 12);
    }
    left = Math.max(8, Math.min(rect.left, window.innerWidth - ttW - 16));
    tt.style.position = 'absolute';
    tt.style.top = top + 'px';
    tt.style.left = left + 'px';
  }

  function showStep(idx) {
    if (idx < 0 || idx >= tourStepList.length) { endTour(); return; }
    tourCurrentStep = idx;
    var step = tourStepList[idx];
    var total = tourStepList.length;

    if (tourPrevHighlight) tourPrevHighlight.classList.remove('tour-highlight');

    if (step.action) step.action();

    function doShow() {
      var el = document.querySelector(step.selector);
      if (!el) {
        // 要素が見つからない場合はスキップ
        if (idx + 1 < tourStepList.length) { showStep(idx + 1); }
        else { endTour(); }
        return;
      }

      el.classList.add('tour-highlight');
      tourPrevHighlight = el;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });

      var btnsHtml =
        '<button class="tour-btn tour-btn-skip" onclick="endTour()">閉じる</button>';
      if (idx > 0) {
        btnsHtml += '<button class="tour-btn tour-btn-skip" onclick="window._tourPrev()">戻る</button>';
      }
      btnsHtml += '<button class="tour-btn tour-btn-next" onclick="window._tourNext()">' +
        (idx === total - 1 ? '完了' : '次へ') + '</button>';

      tourTooltip.innerHTML =
        '<h4>' + step.title + '</h4><p>' + step.text + '</p>' +
        '<div class="tour-tooltip-footer">' +
          '<span class="tour-step-info">' + (idx + 1) + ' / ' + total + '</span>' +
          '<div class="tour-btns">' + btnsHtml + '</div>' +
        '</div>';
      tourTooltip.style.display = 'block';
      tourOverlay.style.display = 'block';

      setTimeout(function () { positionTooltip(el); }, 150);
    }

    if (step.action) {
      setTimeout(doShow, 200);
    } else {
      doShow();
    }
  }

  function startTour() {
    var allSteps = steps();
    if (!allSteps.length) return;
    // ツアー開始時に有効ステップを確定（以後変更しない）
    tourStepList = [];
    for (var i = 0; i < allSteps.length; i++) {
      var el = document.querySelector(allSteps[i].selector);
      if (el) {
        tourStepList.push(allSteps[i]);
      }
    }
    if (!tourStepList.length) return;
    createOverlay();
    tourCurrentStep = 0;
    showStep(0);
  }

  function endTour() {
    if (tourPrevHighlight) tourPrevHighlight.classList.remove('tour-highlight');
    if (tourOverlay) tourOverlay.style.display = 'none';
    if (tourTooltip) tourTooltip.style.display = 'none';
    tourStepList = [];
    try { localStorage.setItem(storageKey(), '1'); } catch (e) {}
  }

  // Expose globally
  window.startTour = startTour;
  window.endTour = endTour;
  window._tourNext = function () { showStep(tourCurrentStep + 1); };
  window._tourPrev = function () { showStep(tourCurrentStep - 1); };

  // Auto-show on first visit (after 800ms) — respects TOUR_AUTO_START setting
  document.addEventListener('DOMContentLoaded', function () {
    if (window.TOUR_AUTO_START === false) return;
    try {
      if (!localStorage.getItem(storageKey()) && steps().length) {
        setTimeout(startTour, 800);
      }
    } catch (e) {}
  });
})();
