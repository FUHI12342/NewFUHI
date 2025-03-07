from django import template
from django.urls import reverse

register = template.Library()

@register.inclusion_tag('admin/custom_sidebar.html', takes_context=True)
def custom_sidebar(context):
    request = context.get('request')
    app_list = context.get('available_apps', [])
    
    # 除外するモデルのリスト
    exclude_models = ['ModelNameToExclude']

    # 除外するモデルをフィルタリング
    for app in app_list:
        app['models'] = [model for model in app['models'] if model['object_name'] not in exclude_models]

    return {
        'analyze_customers_url': reverse('analyze_customers'),
        'app_list': app_list,
    }