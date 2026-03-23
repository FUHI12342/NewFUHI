"""HTML sanitization helpers using bleach."""
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


def sanitize_url(url: str) -> str:
    """Ensure URL uses http/https scheme only (prevent javascript: XSS)."""
    if not url:
        return url
    url = url.strip()
    if url.lower().startswith(('http://', 'https://')):
        return url
    return ''
