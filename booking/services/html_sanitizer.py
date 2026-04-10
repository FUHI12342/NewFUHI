"""HTML sanitization helpers using bleach."""
import re

import bleach

# Allowed tags for rich-text HTML fields (notice content, policies, etc.)
RICH_TEXT_TAGS = [
    'p', 'br', 'strong', 'em', 'b', 'i', 'u', 's',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li',
    'a', 'img',
    'blockquote', 'pre', 'code',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'div', 'span', 'hr',
]
RICH_TEXT_ATTRS = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'width', 'height'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan'],
    'div': ['class', 'style'],
    'span': ['class', 'style'],
}
RICH_TEXT_PROTOCOLS = ['http', 'https', 'mailto']

# Allowed tags for Google Maps embed field (iframe only)
EMBED_TAGS = ['iframe']
EMBED_ATTRS = {
    'iframe': ['src', 'width', 'height', 'frameborder', 'allowfullscreen',
               'loading', 'referrerpolicy', 'style'],
}
EMBED_PROTOCOLS = ['https']


def sanitize_rich_text(html: str) -> str:
    """Sanitize rich-text HTML, stripping dangerous tags/attrs."""
    if not html:
        return html
    return bleach.clean(
        html,
        tags=RICH_TEXT_TAGS,
        attributes=RICH_TEXT_ATTRS,
        protocols=RICH_TEXT_PROTOCOLS,
        strip=True,
    )


def sanitize_embed(html: str) -> str:
    """Sanitize embed HTML, allowing only iframes with https src."""
    if not html:
        return html
    return bleach.clean(
        html,
        tags=EMBED_TAGS,
        attributes=EMBED_ATTRS,
        protocols=EMBED_PROTOCOLS,
        strip=True,
    )


# --- Page Builder sanitization (GrapesJS) ---
# Permissive tag list for visual page builder output.
# Allows structural/styling tags but strips <script>, <object>, <embed>, etc.
PAGE_BUILDER_TAGS = RICH_TEXT_TAGS + [
    'section', 'article', 'header', 'footer', 'nav', 'main', 'aside',
    'figure', 'figcaption', 'picture', 'source', 'video', 'audio',
    'button', 'label', 'input', 'select', 'option', 'textarea', 'form',
    'iframe',
]
PAGE_BUILDER_ATTRS = {
    **RICH_TEXT_ATTRS,
    '*': ['class', 'id', 'style', 'data-gjs-type', 'title', 'role',
          'aria-label', 'aria-hidden', 'tabindex'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'width', 'height', 'loading', 'srcset', 'sizes'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allowfullscreen',
               'loading', 'referrerpolicy', 'style'],
    'source': ['src', 'srcset', 'type', 'media'],
    'video': ['src', 'width', 'height', 'controls', 'autoplay', 'muted',
              'loop', 'poster', 'preload'],
    'audio': ['src', 'controls', 'autoplay', 'muted', 'loop', 'preload'],
    'input': ['type', 'name', 'value', 'placeholder', 'required', 'disabled'],
    'select': ['name', 'required', 'disabled'],
    'option': ['value', 'selected'],
    'textarea': ['name', 'placeholder', 'rows', 'cols', 'required'],
    'form': ['action', 'method'],
    'button': ['type', 'disabled'],
    'td': ['colspan', 'rowspan', 'style'],
    'th': ['colspan', 'rowspan', 'style'],
    'label': ['for'],
}

# Dangerous CSS patterns to strip
_DANGEROUS_CSS_RE = re.compile(
    r'expression\s*\(|'           # IE expression()
    r'javascript\s*:|'            # javascript: in url()
    r'vbscript\s*:|'              # vbscript:
    r'-moz-binding\s*:|'          # Firefox XBL binding
    r'behavior\s*:',              # IE behavior
    re.IGNORECASE,
)


def sanitize_page_builder_html(html: str) -> str:
    """Sanitize GrapesJS page builder HTML output.

    Allows rich structural tags for visual page building but strips
    <script>, event handlers (onclick, onerror, etc.), and javascript: URIs.
    """
    if not html:
        return html
    return bleach.clean(
        html,
        tags=PAGE_BUILDER_TAGS,
        attributes=PAGE_BUILDER_ATTRS,
        protocols=RICH_TEXT_PROTOCOLS + ['https'],
        strip=True,
    )


def sanitize_css(css: str) -> str:
    """Sanitize CSS content, stripping dangerous patterns.

    Removes expression(), javascript:, vbscript:, -moz-binding, behavior.
    """
    if not css:
        return css
    return _DANGEROUS_CSS_RE.sub('/* sanitized */', css)


def sanitize_url(url: str) -> str:
    """Ensure URL uses http/https scheme only (prevent javascript: XSS)."""
    if not url:
        return url
    url = url.strip()
    if url.lower().startswith(('http://', 'https://')):
        return url
    return ''
