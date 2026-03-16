/**
 * TinyMCE initialization for Django admin Notice editor.
 * Waits for TinyMCE CDN to load, then initializes on .tinymce-editor textareas.
 */
(function () {
  "use strict";

  function initTinyMCE() {
    if (typeof tinymce === "undefined") {
      setTimeout(initTinyMCE, 200);
      return;
    }
    tinymce.init({
      selector: "textarea.tinymce-editor",
      height: 500,
      menubar: "file edit view insert format tools table",
      plugins: [
        "advlist",
        "autolink",
        "lists",
        "link",
        "image",
        "charmap",
        "preview",
        "anchor",
        "searchreplace",
        "visualblocks",
        "code",
        "fullscreen",
        "insertdatetime",
        "media",
        "table",
        "help",
        "wordcount",
      ],
      toolbar:
        "undo redo | blocks | bold italic forecolor backcolor | " +
        "alignleft aligncenter alignright alignjustify | " +
        "bullist numlist outdent indent | link image media | " +
        "removeformat | code fullscreen | help",
      content_style:
        "body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 14px; }",
      language: "ja",
      promotion: false,
      branding: false,
      relative_urls: false,
      remove_script_host: false,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTinyMCE);
  } else {
    initTinyMCE();
  }
})();
