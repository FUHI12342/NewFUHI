"""
SEO用カスタムテンプレートタグ
hreflang タグ生成のための translate_url テンプレートタグを提供する。
Django 4.2 には translate_url テンプレートタグが存在しないため独自実装。
"""
from django import template
from django.urls import translate_url as django_translate_url

register = template.Library()


@register.simple_tag(takes_context=True)
def hreflang_url(context, lang_code):
    """
    現在のリクエストURLを指定言語に変換して返す。

    使用例:
        {% load seo_tags %}
        {% hreflang_url "en" %}
        → /en/path/to/current/page/
    """
    request = context.get("request")
    if request is None:
        return ""
    # translate_url は URL の言語プレフィックスを置き換える
    # 変換できない場合は元の URL を返す
    return django_translate_url(request.path, lang_code)
