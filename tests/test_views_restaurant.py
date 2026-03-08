"""
tests/test_views_restaurant.py
Table order views: TableMenuView, TableCartView, TableOrderView,
TableCheckoutView, TableOrderHistoryView.
"""
import pytest
from django.urls import reverse
from booking.models import Product, Order, OrderItem, PaymentMethod


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


# ------------------------------------------------------------------
# TableMenuView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableMenuView:
    def test_get_returns_200(self, api_client, table_seat, product):
        url = reverse('table:table_menu', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200

    def test_context_has_products(self, api_client, table_seat, product):
        url = reverse('table:table_menu', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        product_ids = [p['id'] for p in resp.context['products']]
        assert product.id in product_ids

    def test_invalid_table_returns_404(self, api_client):
        import uuid
        fake_id = uuid.uuid4()
        url = reverse('table:table_menu', kwargs={'table_id': fake_id})
        resp = api_client.get(url)
        assert resp.status_code == 404

    def test_filter_by_category(self, api_client, table_seat, product, category):
        url = reverse('table:table_menu', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url, {'category': category.pk})
        assert resp.status_code == 200
        for p in resp.context['products']:
            assert p['category_id'] == category.pk


# ------------------------------------------------------------------
# TableCartView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableCartView:
    def test_empty_cart(self, api_client, table_seat):
        url = reverse('table:table_cart', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert resp.context['cart_items'] == []
        assert resp.context['total'] == 0

    def test_cart_with_items_in_session(self, api_client, table_seat, product):
        cart_key = f'table_cart_{table_seat.pk}'
        session = api_client.session
        session[cart_key] = {
            str(product.id): {
                'name': product.name,
                'price': product.price,
                'qty': 3,
            }
        }
        session.save()

        url = reverse('table:table_cart', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert len(resp.context['cart_items']) == 1
        assert resp.context['total'] == product.price * 3


# ------------------------------------------------------------------
# TableOrderView (POST)
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableOrderView:
    def test_creates_order_and_clears_cart(self, api_client, table_seat, product):
        cart_key = f'table_cart_{table_seat.pk}'
        session = api_client.session
        session[cart_key] = {
            str(product.id): {
                'name': product.name,
                'price': product.price,
                'qty': 2,
            }
        }
        session.save()

        url = reverse('table:table_order', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(url)
        assert resp.status_code == 302  # redirect to history

        order = Order.objects.filter(table_seat=table_seat).first()
        assert order is not None
        assert order.items.count() == 1
        assert order.items.first().qty == 2

        # Cart should be cleared
        session = api_client.session
        assert session.get(cart_key) == {}

        # Stock should be deducted
        product.refresh_from_db()
        assert product.stock == 98  # 100 - 2

    def test_empty_cart_redirects_to_menu(self, api_client, table_seat):
        url = reverse('table:table_order', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(url)
        assert resp.status_code == 302
        assert str(table_seat.pk) in resp.url

    def test_insufficient_stock_redirects(self, api_client, table_seat, product):
        product.stock = 1
        product.save()

        cart_key = f'table_cart_{table_seat.pk}'
        session = api_client.session
        session[cart_key] = {
            str(product.id): {
                'name': product.name,
                'price': product.price,
                'qty': 5,
            }
        }
        session.save()

        url = reverse('table:table_order', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(url)
        # Should redirect back to cart with error
        assert resp.status_code == 302


# ------------------------------------------------------------------
# TableCheckoutView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableCheckoutView:
    def _setup_order_session(self, api_client, table_seat, product):
        """Helper: create an order and put it in session."""
        order = Order.objects.create(
            store=table_seat.store,
            table_seat=table_seat,
            table_label=table_seat.label,
            status=Order.STATUS_OPEN,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            qty=1,
            unit_price=product.price,
        )
        orders_key = f'table_orders_{table_seat.pk}'
        session = api_client.session
        session[orders_key] = [order.id]
        session.save()
        return order

    def test_get_shows_checkout(self, api_client, table_seat, product):
        self._setup_order_session(api_client, table_seat, product)
        url = reverse('table:table_checkout', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert resp.context['grand_total'] == product.price

    def test_post_cash_payment(self, api_client, table_seat, product):
        self._setup_order_session(api_client, table_seat, product)
        pm = PaymentMethod.objects.create(
            store=table_seat.store,
            method_type='cash',
            display_name='現金',
            is_enabled=True,
        )
        url = reverse('table:table_checkout', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(url, {'payment_method_id': pm.pk})
        assert resp.status_code == 200
        order = Order.objects.filter(table_seat=table_seat).first()
        assert order.status == Order.STATUS_CLOSED

    def test_post_without_payment_method_redirects(self, api_client, table_seat, product):
        self._setup_order_session(api_client, table_seat, product)
        url = reverse('table:table_checkout', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(url, {})
        assert resp.status_code == 302


# ------------------------------------------------------------------
# TableOrderHistoryView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableOrderHistoryView:
    def test_shows_order_history(self, api_client, table_seat, product):
        order = Order.objects.create(
            store=table_seat.store,
            table_seat=table_seat,
            table_label=table_seat.label,
            status=Order.STATUS_OPEN,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            qty=2,
            unit_price=product.price,
        )
        orders_key = f'table_orders_{table_seat.pk}'
        session = api_client.session
        session[orders_key] = [order.id]
        session.save()

        url = reverse('table:table_history', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert len(resp.context['orders']) == 1
        assert resp.context['grand_total'] == product.price * 2

    def test_empty_history(self, api_client, table_seat):
        url = reverse('table:table_history', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert resp.context['grand_total'] == 0
