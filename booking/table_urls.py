from django.urls import path
from .views import (
    TableMenuView,
    TableCartView,
    TableOrderView,
    TableOrderHistoryView,
    TableCheckoutView,
)

app_name = 'table'

urlpatterns = [
    path('<uuid:table_id>/', TableMenuView.as_view(), name='table_menu'),
    path('<uuid:table_id>/cart/', TableCartView.as_view(), name='table_cart'),
    path('<uuid:table_id>/order/', TableOrderView.as_view(), name='table_order'),
    path('<uuid:table_id>/history/', TableOrderHistoryView.as_view(), name='table_history'),
    path('<uuid:table_id>/checkout/', TableCheckoutView.as_view(), name='table_checkout'),
]
