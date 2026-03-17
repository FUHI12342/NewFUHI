"""在庫管理ダッシュボード — EC商品/飲食メニューの在庫一覧・入荷登録"""

from django import forms
from django.contrib import messages
from django.db.models import F
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, FormView

from .models import Product, Category, StockMovement, Staff, Store
from .views_restaurant_dashboard import AdminSidebarMixin


class InventoryDashboardView(AdminSidebarMixin, TemplateView):
    """在庫一覧ダッシュボード（管理画面カスタムビュー）"""
    template_name = 'admin/booking/inventory_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = self._get_store()
        if not store:
            ctx['products'] = []
            ctx['categories'] = []
            return ctx

        category_filter = self.request.GET.get('category', 'all')
        low_only = self.request.GET.get('low_only') == '1'

        products = Product.objects.filter(
            store=store, is_active=True,
        ).select_related('category').order_by('category__sort_order', 'name')

        if category_filter == 'ec':
            products = products.filter(category__is_restaurant_menu=False)
        elif category_filter == 'restaurant':
            products = products.filter(category__is_restaurant_menu=True)

        if low_only:
            products = products.filter(stock__lte=F('low_stock_threshold'))

        categories = Category.objects.filter(store=store).order_by('sort_order')

        # Stats
        total = products.count()
        low_stock = products.filter(stock__lte=F('low_stock_threshold')).count()
        out_of_stock = products.filter(stock__lte=0).count()

        ctx.update({
            'products': products,
            'categories': categories,
            'category_filter': category_filter,
            'low_only': low_only,
            'total_count': total,
            'low_stock_count': low_stock,
            'out_of_stock_count': out_of_stock,
            'title': _('在庫管理ダッシュボード'),
            'has_permission': True,
            'site_header': _('管理サイト'),
        })
        return ctx

    def _get_store(self):
        user = self.request.user
        if user.is_superuser:
            return Store.objects.first()
        try:
            return user.staff.store
        except (Staff.DoesNotExist, AttributeError):
            return Store.objects.first()


class StockInForm(forms.Form):
    """入荷登録フォーム"""
    product = forms.ModelChoiceField(
        queryset=Product.objects.none(),
        label=_('商品'),
    )
    quantity = forms.IntegerField(
        min_value=1, max_value=9999,
        label=_('入荷数量'),
    )
    note = forms.CharField(
        max_length=200, required=False,
        label=_('メモ'),
        widget=forms.TextInput(attrs={'placeholder': _('入荷メモ（任意）')}),
    )

    def __init__(self, *args, store=None, **kwargs):
        super().__init__(*args, **kwargs)
        if store:
            self.fields['product'].queryset = Product.objects.filter(
                store=store, is_active=True,
            ).select_related('category').order_by('category__sort_order', 'name')


class StockInFormView(AdminSidebarMixin, FormView):
    """入荷登録処理"""
    template_name = 'admin/booking/inventory_dashboard.html'
    form_class = StockInForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['store'] = self._get_store()
        return kwargs

    def form_valid(self, form):
        product = form.cleaned_data['product']
        quantity = form.cleaned_data['quantity']
        note = form.cleaned_data['note'] or _('管理画面から入荷登録')

        staff = None
        try:
            staff = self.request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            pass

        StockMovement.objects.create(
            store=product.store,
            product=product,
            movement_type=StockMovement.TYPE_IN,
            qty=quantity,
            by_staff=staff,
            note=note,
        )
        product.stock = F('stock') + quantity
        product.save(update_fields=['stock'])

        messages.success(
            self.request,
            _('%(name)s に %(qty)d 個入荷しました。') % {
                'name': product.name, 'qty': quantity,
            },
        )
        return redirect('/admin/inventory/')

    def form_invalid(self, form):
        messages.error(self.request, _('入力内容を確認してください。'))
        return redirect('/admin/inventory/')

    def _get_store(self):
        user = self.request.user
        if user.is_superuser:
            return Store.objects.first()
        try:
            return user.staff.store
        except (Staff.DoesNotExist, AttributeError):
            return Store.objects.first()
