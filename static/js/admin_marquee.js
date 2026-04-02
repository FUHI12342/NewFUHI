/**
 * admin_marquee.js
 *
 * Detects overflowing text in Django admin changelist table cells (#result_list td)
 * and wraps their content in a <span class="admin-marquee-inner"> so the CSS
 * marquee animation can scroll the text on hover.
 *
 * Only cells whose scrollWidth exceeds clientWidth are affected.
 * Cells containing form controls (input, select, textarea) are skipped.
 */
(function () {
  "use strict";

  function initMarquee() {
    var cells = document.querySelectorAll("#result_list td");
    if (!cells.length) {
      return;
    }

    cells.forEach(function (td) {
      // Skip cells that contain form controls (editable fields)
      if (td.querySelector("input, select, textarea")) {
        return;
      }
      // Skip cells that are already processed
      if (td.classList.contains("admin-marquee-ready")) {
        return;
      }
      // Check if the text is overflowing
      if (td.scrollWidth <= td.clientWidth) {
        return;
      }

      // Store the original title attribute for tooltip
      var textContent = td.textContent.trim();
      if (!td.getAttribute("title")) {
        td.setAttribute("title", textContent);
      }

      // Wrap the inner content in a span for animation
      var inner = document.createElement("span");
      inner.className = "admin-marquee-inner";

      // Move all child nodes into the wrapper span
      while (td.firstChild) {
        inner.appendChild(td.firstChild);
      }
      td.appendChild(inner);
      td.classList.add("admin-marquee-ready");
    });
  }

  // Run on DOMContentLoaded or immediately if already loaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initMarquee);
  } else {
    initMarquee();
  }
})();
