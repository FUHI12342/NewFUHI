"""
tests/test_line_segment.py
Tests for booking/services/line_segment.py:
  - _compute_segment (vip by visits, vip by spent, regular, dormant, new)
  - recompute_segments (updates DB)
  - get_customers_by_segment (filtering by segment and store)
  - send_segment_message (batch send with mocked push_text)
"""
import pytest
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from booking.models.line_customer import LineCustomer


# ==============================================================
# Helpers
# ==============================================================

def _make_customer(store, line_user_id, visit_count=0, total_spent=0,
                   last_visit_delta_days=None, segment='new'):
    """Create a LineCustomer for segment testing."""
    from booking.services.line_bot_service import get_customer_or_create

    customer, _ = get_customer_or_create(
        line_user_id, display_name=f'User_{line_user_id[-4:]}', store=store,
    )
    update_fields = {
        'visit_count': visit_count,
        'total_spent': total_spent,
        'segment': segment,
        'is_friend': True,
    }
    if last_visit_delta_days is not None:
        update_fields['last_visit_at'] = timezone.now() - timedelta(days=last_visit_delta_days)
    LineCustomer.objects.filter(pk=customer.pk).update(**update_fields)
    customer.refresh_from_db()
    return customer


# ==============================================================
# _compute_segment
# ==============================================================

@pytest.mark.django_db
class TestComputeSegment:
    def test_vip_by_visits(self, store):
        """visit_count >= 5 returns 'vip'."""
        from booking.services.line_segment import _compute_segment

        customer = _make_customer(store, 'U_seg_vip_v', visit_count=5)
        cutoff = timezone.now() - timedelta(days=90)
        assert _compute_segment(customer, cutoff) == 'vip'

    def test_vip_by_spent(self, store):
        """total_spent >= 30000 returns 'vip'."""
        from booking.services.line_segment import _compute_segment

        customer = _make_customer(store, 'U_seg_vip_s', total_spent=30000)
        cutoff = timezone.now() - timedelta(days=90)
        assert _compute_segment(customer, cutoff) == 'vip'

    def test_regular(self, store):
        """visit_count >= 2 with recent visit returns 'regular'."""
        from booking.services.line_segment import _compute_segment

        customer = _make_customer(
            store, 'U_seg_regular', visit_count=2, last_visit_delta_days=30,
        )
        cutoff = timezone.now() - timedelta(days=90)
        assert _compute_segment(customer, cutoff) == 'regular'

    def test_dormant(self, store):
        """last_visit > 90 days ago returns 'dormant'."""
        from booking.services.line_segment import _compute_segment

        customer = _make_customer(
            store, 'U_seg_dormant', visit_count=2, last_visit_delta_days=91,
        )
        cutoff = timezone.now() - timedelta(days=90)
        assert _compute_segment(customer, cutoff) == 'dormant'

    def test_new(self, store):
        """visit_count <= 1 returns 'new'."""
        from booking.services.line_segment import _compute_segment

        customer = _make_customer(store, 'U_seg_new', visit_count=1)
        cutoff = timezone.now() - timedelta(days=90)
        assert _compute_segment(customer, cutoff) == 'new'


# ==============================================================
# recompute_segments
# ==============================================================

@pytest.mark.django_db
class TestRecomputeSegments:
    def test_recompute_segments_updates_db(self, store):
        """recompute_segments updates segment values in the DB."""
        from booking.services.line_segment import recompute_segments

        # Create customer with segment='new' but VIP-qualifying stats
        customer = _make_customer(
            store, 'U_recomp_001', visit_count=10, total_spent=50000, segment='new',
        )
        assert customer.segment == 'new'

        updated = recompute_segments()
        assert updated >= 1

        customer.refresh_from_db()
        assert customer.segment == 'vip'


# ==============================================================
# get_customers_by_segment
# ==============================================================

@pytest.mark.django_db
class TestGetCustomersBySegment:
    def test_filters_by_segment_and_store(self, store):
        """Returns only customers matching segment and store."""
        from booking.services.line_segment import get_customers_by_segment

        _make_customer(store, 'U_filter_vip1', segment='vip')
        _make_customer(store, 'U_filter_new1', segment='new')

        # Create another store with a VIP customer
        other_store = Store.objects.create(
            name='Other Store', address='Osaka', business_hours='10:00-18:00',
        )
        _make_customer(other_store, 'U_filter_vip2', segment='vip')

        # Filter VIP for original store
        qs = get_customers_by_segment('vip', store_id=store.pk)
        assert qs.count() == 1
        assert qs.first().display_name == 'User_vip1'

        # Filter VIP across all stores
        qs_all = get_customers_by_segment('vip')
        assert qs_all.count() == 2


# ==============================================================
# send_segment_message
# ==============================================================

@pytest.mark.django_db
class TestSendSegmentMessage:
    @patch('booking.services.line_bot_service.push_text', return_value=True)
    def test_send_segment_message(self, mock_push, store):
        """Sends messages to specified customers and counts results."""
        from booking.services.line_segment import send_segment_message

        c1 = _make_customer(store, 'U_batch_001')
        c2 = _make_customer(store, 'U_batch_002')

        results = send_segment_message([c1.pk, c2.pk], 'Campaign message')

        assert results['sent'] == 2
        assert results['failed'] == 0
        assert mock_push.call_count == 2

    @patch('booking.services.line_bot_service.push_text')
    def test_send_segment_message_partial_failure(self, mock_push, store):
        """Counts failures when some push_text calls fail."""
        from booking.services.line_segment import send_segment_message

        mock_push.side_effect = [True, False]

        c1 = _make_customer(store, 'U_partial_001')
        c2 = _make_customer(store, 'U_partial_002')

        results = send_segment_message([c1.pk, c2.pk], 'Campaign message')

        assert results['sent'] == 1
        assert results['failed'] == 1


# Need Store import for test_filters_by_segment_and_store
from booking.models import Store
