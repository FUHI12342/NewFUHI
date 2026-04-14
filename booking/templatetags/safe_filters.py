"""カスタムテンプレートフィルタ: XSS防止のためのHTML/JSONサニタイズ"""
import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# 許可するHTMLタグ
ALLOWED_TAGS = {
    'p', 'br', 'strong', 'em', 'u', 'a', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'div', 'span',
    'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'blockquote', 'pre', 'code', 'hr', 'section', 'article',
    'header', 'footer', 'nav', 'main', 'figure', 'figcaption',
}

# 許可する属性
ALLOWED_ATTRS = {
    'class', 'id', 'style', 'href', 'src', 'alt', 'title',
    'width', 'height', 'target', 'rel', 'colspan', 'rowspan',
    'data-gjs-type', 'data-gjs-highlightable',
}

# 危険なパターン
DANGEROUS_PATTERNS = [
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'vbscript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # onclick, onerror, etc.
    re.compile(r'<script', re.IGNORECASE),
    re.compile(r'</script', re.IGNORECASE),
]


@register.filter(name='safe_html')
def safe_html(value):
    """HTMLコンテンツをサニタイズして安全にレンダリング。

    scriptタグ、イベントハンドラ、javascript: URLを除去。
    """
    if not value:
        return ''
    value = str(value)
    # Remove script tags entirely
    value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.DOTALL | re.IGNORECASE)
    # Remove event handlers (onclick, onerror, etc.)
    value = re.sub(r'\s+on\w+\s*=\s*["\'][^"\']*["\']', '', value, flags=re.IGNORECASE)
    value = re.sub(r'\s+on\w+\s*=\s*\S+', '', value, flags=re.IGNORECASE)
    # Remove javascript: and vbscript: URLs
    value = re.sub(r'javascript\s*:', '', value, flags=re.IGNORECASE)
    value = re.sub(r'vbscript\s*:', '', value, flags=re.IGNORECASE)
    return mark_safe(value)


@register.filter(name='safe_json')
def safe_json(value):
    """JSONデータを安全にJavaScript変数に埋め込む。

    </script>インジェクションを防止。
    """
    if not value:
        return mark_safe('{}')
    json_str = str(value)
    # Prevent </script> injection in JSON
    json_str = json_str.replace('</script>', '<\\/script>')
    json_str = json_str.replace('</Script>', '<\\/Script>')
    return mark_safe(json_str)
