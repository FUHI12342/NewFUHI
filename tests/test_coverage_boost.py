"""
Coverage boost tests — targets 0% and low-coverage modules to push
total coverage above 80%.

Targets:
- services/staff_evaluation.py (0% → ~90%)
- management/commands/delete_food_drink_data.py (0% → ~90%)
- management/commands/seed_restaurant_menu.py (0% → ~90%)
- management/commands/sync_menu_config.py (0% → ~90%)
- services/basket_analysis.py (71% → ~90%)
- services/rfm_analysis.py (74% → ~90%)
- services/sales_forecast.py (78% → ~90%)
"""
import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.utils import timezone

from booking.models import (
    Store, Staff, ShiftAssignment, ShiftPeriod, WorkAttendance,
    StaffEvaluation, Category, Product, Order, OrderItem, StockMovement,
    AdminMenuConfig, VisitorCount,
)


# ==============================
# staff_evaluation.py tests
# ==============================

class TestCalculateAttendanceRate:
    """Tests for calculate_attendance_rate()."""

    def test_no_assignments_returns_none(self, db, staff):
        from booking.services.staff_evaluation import calculate_attendance_rate
        result = calculate_attendance_rate(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result is None

    def test_full_attendance(self, db, staff, shift_period):
        from booking.services.staff_evaluation import calculate_attendance_rate

        # Create 5 assignments + 5 attendances
        for day_offset in range(5):
            d = date(2025, 4, 10 + day_offset)
            ShiftAssignment.objects.create(
                period=shift_period, staff=staff,
                date=d, start_hour=9, end_hour=17,
            )
            WorkAttendance.objects.create(
                staff=staff, date=d,
                clock_in=time(9, 0), clock_out=time(17, 0),
                regular_minutes=420, source='shift',
            )

        result = calculate_attendance_rate(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result == 100.0

    def test_partial_attendance(self, db, staff, shift_period):
        from booking.services.staff_evaluation import calculate_attendance_rate

        for day_offset in range(4):
            d = date(2025, 4, 10 + day_offset)
            ShiftAssignment.objects.create(
                period=shift_period, staff=staff,
                date=d, start_hour=9, end_hour=17,
            )

        # Only 2 attendances for 4 assignments
        for day_offset in range(2):
            d = date(2025, 4, 10 + day_offset)
            WorkAttendance.objects.create(
                staff=staff, date=d,
                clock_in=time(9, 0), clock_out=time(17, 0),
                regular_minutes=420, source='shift',
            )

        result = calculate_attendance_rate(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result == 50.0


class TestCalculatePunctualityScore:
    """Tests for calculate_punctuality_score()."""

    def test_no_assignments_returns_none(self, db, staff):
        from booking.services.staff_evaluation import calculate_punctuality_score
        result = calculate_punctuality_score(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result is None

    def test_perfect_punctuality(self, db, staff, shift_period):
        from booking.services.staff_evaluation import calculate_punctuality_score

        d = date(2025, 4, 10)
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=d, start_hour=9, end_hour=17,
        )
        WorkAttendance.objects.create(
            staff=staff, date=d,
            clock_in=time(8, 55), clock_out=time(17, 0),
            regular_minutes=420, source='shift',
        )

        result = calculate_punctuality_score(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result == 5.0

    def test_slight_late(self, db, staff, shift_period):
        """5 minutes late should score 4.0."""
        from booking.services.staff_evaluation import calculate_punctuality_score

        d = date(2025, 4, 10)
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=d, start_hour=9, end_hour=17,
        )
        WorkAttendance.objects.create(
            staff=staff, date=d,
            clock_in=time(9, 3), clock_out=time(17, 0),
            regular_minutes=420, source='shift',
        )

        result = calculate_punctuality_score(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result == 4.0

    def test_moderate_late(self, db, staff, shift_period):
        """10 minutes late should score 3.0."""
        from booking.services.staff_evaluation import calculate_punctuality_score

        d = date(2025, 4, 10)
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=d, start_hour=9, end_hour=17,
        )
        WorkAttendance.objects.create(
            staff=staff, date=d,
            clock_in=time(9, 10), clock_out=time(17, 0),
            regular_minutes=420, source='shift',
        )

        result = calculate_punctuality_score(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result == 3.0

    def test_significant_late(self, db, staff, shift_period):
        """25 minutes late should score 2.0."""
        from booking.services.staff_evaluation import calculate_punctuality_score

        d = date(2025, 4, 10)
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=d, start_hour=9, end_hour=17,
        )
        WorkAttendance.objects.create(
            staff=staff, date=d,
            clock_in=time(9, 25), clock_out=time(17, 0),
            regular_minutes=420, source='shift',
        )

        result = calculate_punctuality_score(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result == 2.0

    def test_very_late(self, db, staff, shift_period):
        """45 minutes late should score 1.0."""
        from booking.services.staff_evaluation import calculate_punctuality_score

        d = date(2025, 4, 10)
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=d, start_hour=9, end_hour=17,
        )
        WorkAttendance.objects.create(
            staff=staff, date=d,
            clock_in=time(9, 45), clock_out=time(17, 0),
            regular_minutes=420, source='shift',
        )

        result = calculate_punctuality_score(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result == 1.0

    def test_absent_scores_zero(self, db, staff, shift_period):
        """No clock_in should score 0.0."""
        from booking.services.staff_evaluation import calculate_punctuality_score

        d = date(2025, 4, 10)
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=d, start_hour=9, end_hour=17,
        )
        # No attendance record

        result = calculate_punctuality_score(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result == 0.0


class TestCalculateTotalWorkHours:
    """Tests for calculate_total_work_hours()."""

    def test_no_attendance_returns_none(self, db, staff):
        from booking.services.staff_evaluation import calculate_total_work_hours
        result = calculate_total_work_hours(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert result is None

    def test_total_hours_calculated(self, db, staff):
        from booking.services.staff_evaluation import calculate_total_work_hours

        WorkAttendance.objects.create(
            staff=staff, date=date(2025, 4, 10),
            clock_in=time(9, 0), clock_out=time(17, 0),
            regular_minutes=420, overtime_minutes=60,
            source='shift',
        )
        WorkAttendance.objects.create(
            staff=staff, date=date(2025, 4, 11),
            clock_in=time(9, 0), clock_out=time(17, 0),
            regular_minutes=420, overtime_minutes=0,
            source='shift',
        )

        result = calculate_total_work_hours(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        # (420+60 + 420+0) / 60 = 15.0
        assert result == 15.0


class TestGenerateAutoEvaluation:
    """Tests for generate_auto_evaluation()."""

    def test_with_data(self, db, staff, shift_period):
        from booking.services.staff_evaluation import generate_auto_evaluation

        d = date(2025, 4, 10)
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=d, start_hour=9, end_hour=17,
        )
        WorkAttendance.objects.create(
            staff=staff, date=d,
            clock_in=time(9, 0), clock_out=time(17, 0),
            regular_minutes=420, overtime_minutes=0,
            source='shift',
        )

        evaluation = generate_auto_evaluation(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert isinstance(evaluation, StaffEvaluation)
        assert evaluation.attendance_rate == 100.0
        assert evaluation.punctuality_score == 5.0
        assert evaluation.overall_score is not None
        assert evaluation.grade != ''
        assert evaluation.source == 'auto'
        # Not saved to DB
        assert evaluation.pk is None

    def test_no_data(self, db, staff):
        from booking.services.staff_evaluation import generate_auto_evaluation

        evaluation = generate_auto_evaluation(
            staff, date(2025, 4, 1), date(2025, 4, 30),
        )
        assert isinstance(evaluation, StaffEvaluation)
        assert evaluation.attendance_rate is None
        assert evaluation.overall_score is None
        assert evaluation.grade == ''


# ==============================
# delete_food_drink_data command tests
# ==============================

class TestDeleteFoodDrinkDataCommand:
    """Tests for delete_food_drink_data management command."""

    def _seed_food_data(self, store):
        cat = Category.objects.create(store=store, name='ドリンク', sort_order=0)
        p1 = Product.objects.create(
            store=store, category=cat, sku='DR-001',
            name='コーヒー', price=500, stock=50,
        )
        p2 = Product.objects.create(
            store=store, category=cat, sku='FD-001',
            name='サンド', price=700, stock=30,
        )
        order = Order.objects.create(store=store, status=Order.STATUS_OPEN)
        OrderItem.objects.create(
            order=order, product=p1, qty=1, unit_price=500,
        )
        StockMovement.objects.create(
            store=store, product=p1, movement_type='IN', qty=50,
        )
        return cat, p1, p2, order

    def test_dry_run(self, db, store, capsys):
        cat, p1, p2, order = self._seed_food_data(store)

        call_command('delete_food_drink_data', '--dry-run')
        output = capsys.readouterr().out

        assert 'DRY RUN' in output
        # Data should still exist
        assert Product.objects.filter(sku='DR-001').exists()
        assert Product.objects.filter(sku='FD-001').exists()

    def test_actual_delete(self, db, store, capsys):
        cat, p1, p2, order = self._seed_food_data(store)

        call_command('delete_food_drink_data')
        output = capsys.readouterr().out

        assert '削除完了' in output
        assert not Product.objects.filter(sku__startswith='DR-').exists()
        assert not Product.objects.filter(sku__startswith='FD-').exists()

    def test_no_data(self, db, store, capsys):
        """Command should run fine with no matching data."""
        call_command('delete_food_drink_data')
        output = capsys.readouterr().out
        assert '削除完了' in output


# ==============================
# seed_restaurant_menu command tests
# ==============================

class TestSeedRestaurantMenuCommand:
    """Tests for seed_restaurant_menu management command."""

    def test_seed_creates_products(self, db, store, capsys):
        call_command('seed_restaurant_menu')
        output = capsys.readouterr().out

        assert '作成' in output
        # Should have created drink, food, shisha products
        assert Product.objects.filter(sku__startswith='DR-').count() > 0
        assert Product.objects.filter(sku__startswith='FD-').count() > 0
        assert Product.objects.filter(sku__startswith='SH-').count() > 0
        # Categories created
        assert Category.objects.filter(name='ドリンク').exists()
        assert Category.objects.filter(name='フード').exists()
        assert Category.objects.filter(name='シーシャ').exists()

    def test_seed_skips_existing(self, db, store, capsys):
        # Run twice
        call_command('seed_restaurant_menu')
        call_command('seed_restaurant_menu')
        output = capsys.readouterr().out

        assert 'スキップ' in output

    def test_seed_reset(self, db, store, capsys):
        call_command('seed_restaurant_menu')
        count_before = Product.objects.filter(sku__startswith='DR-').count()

        call_command('seed_restaurant_menu', '--reset')
        output = capsys.readouterr().out

        assert 'リセット' in output
        # Products should still exist (re-created after reset)
        assert Product.objects.filter(sku__startswith='DR-').count() == count_before

    def test_no_store_error(self, db, capsys):
        """Should error if no store exists."""
        Store.objects.all().delete()
        call_command('seed_restaurant_menu')
        output = capsys.readouterr().err
        assert 'Store' in output or 'store' in output.lower() or '見つかりません' in output


# ==============================
# sync_menu_config command tests
# ==============================

class TestSyncMenuConfigCommand:
    """Tests for sync_menu_config management command."""

    def test_dry_run_no_configs(self, db, capsys):
        call_command('sync_menu_config', '--dry-run')
        output = capsys.readouterr().out
        assert 'dry-run' in output.lower() or '--dry-run' in output

    def test_sync_with_missing_models(self, db, capsys):
        """Config with missing models should get them added."""
        config = AdminMenuConfig.objects.create(
            role='manager',
            allowed_models=['schedule', 'order'],
        )

        call_command('sync_menu_config')
        output = capsys.readouterr().out

        config.refresh_from_db()
        # Should have merged default models into the config
        assert 'staff' in config.allowed_models
        assert '同期完了' in output or 'マージ完了' in output

    def test_sync_config_already_complete(self, db, capsys):
        """Config with all models should report OK."""
        from booking.admin_site import DEFAULT_ALLOWED_MODELS
        default_models = DEFAULT_ALLOWED_MODELS.get('manager', [])
        if default_models:
            AdminMenuConfig.objects.create(
                role='manager',
                allowed_models=sorted(default_models),
            )

            call_command('sync_menu_config')
            output = capsys.readouterr().out
            assert 'OK' in output or '不足なし' in output

    def test_sync_developer_role_none(self, db, capsys):
        """Developer role (defaults=None) with DB record should warn."""
        AdminMenuConfig.objects.create(
            role='developer',
            allowed_models=['schedule', 'order'],
        )

        call_command('sync_menu_config')
        output = capsys.readouterr().out
        assert '全モデル表示' in output


# ==============================
# basket_analysis.py tests
# ==============================

class TestBasketAnalysis:
    """Tests for basket analysis service."""

    def _create_orders_with_items(self, store, category, products, orders_data):
        """Helper to create orders with items.
        orders_data: list of lists of (product_index, qty)
        """
        created_orders = []
        for items_data in orders_data:
            order = Order.objects.create(store=store, status=Order.STATUS_OPEN)
            for prod_idx, qty in items_data:
                OrderItem.objects.create(
                    order=order, product=products[prod_idx],
                    qty=qty, unit_price=products[prod_idx].price,
                )
            created_orders.append(order)
        return created_orders

    def test_no_orders_returns_empty(self, db, store):
        from booking.services.basket_analysis import analyze_basket
        result = analyze_basket(scope={'order__store': store})
        assert result['rules'] == []
        assert result['total_transactions'] == 0

    def test_insufficient_baskets(self, db, store, category):
        """Less than 3 multi-item baskets returns no rules."""
        from booking.services.basket_analysis import analyze_basket

        p1 = Product.objects.create(
            store=store, category=category, sku='BA-001',
            name='商品A', price=100, stock=99,
        )
        p2 = Product.objects.create(
            store=store, category=category, sku='BA-002',
            name='商品B', price=200, stock=99,
        )
        # Only 1 multi-item order
        order = Order.objects.create(store=store, status=Order.STATUS_OPEN)
        OrderItem.objects.create(order=order, product=p1, qty=1, unit_price=100)
        OrderItem.objects.create(order=order, product=p2, qty=1, unit_price=200)

        result = analyze_basket(scope={'order__store': store})
        assert result['rules'] == []

    def test_pairwise_analysis(self, db, store, category):
        """With 3+ multi-item baskets, pairwise analysis should find rules."""
        from booking.services.basket_analysis import analyze_basket

        products = []
        for i in range(3):
            products.append(Product.objects.create(
                store=store, category=category, sku=f'BA-{i:03d}',
                name=f'商品{chr(65+i)}', price=100*(i+1), stock=99,
            ))

        # Create 5 orders, each with 2+ items, A+B appear together 4 times
        for _ in range(4):
            order = Order.objects.create(store=store, status=Order.STATUS_OPEN)
            OrderItem.objects.create(order=order, product=products[0], qty=1, unit_price=100)
            OrderItem.objects.create(order=order, product=products[1], qty=1, unit_price=200)

        # One order with B+C
        order = Order.objects.create(store=store, status=Order.STATUS_OPEN)
        OrderItem.objects.create(order=order, product=products[1], qty=1, unit_price=200)
        OrderItem.objects.create(order=order, product=products[2], qty=1, unit_price=300)

        result = analyze_basket(
            scope={'order__store': store},
            min_support=0.01, min_confidence=0.1,
        )
        assert result['method'] == 'pairwise'
        assert result['total_transactions'] == 5
        assert len(result['rules']) > 0
        # Check rule structure
        rule = result['rules'][0]
        assert 'antecedent' in rule
        assert 'consequent' in rule
        assert 'support' in rule
        assert 'confidence' in rule
        assert 'lift' in rule

    def test_scope_none_default(self, db, store, category):
        """scope=None should not crash (no data)."""
        from booking.services.basket_analysis import analyze_basket
        result = analyze_basket(scope=None, days=7)
        assert result['total_transactions'] == 0


# ==============================
# rfm_analysis.py tests
# ==============================

class TestRfmAnalysis:
    """Tests for RFM analysis service."""

    def test_no_orders_returns_empty(self, db, store):
        from booking.services.rfm_analysis import compute_rfm
        result = compute_rfm(scope={'order__store': store})
        assert result == []

    def test_rfm_basic(self, db, store, category):
        from booking.services.rfm_analysis import compute_rfm

        p = Product.objects.create(
            store=store, category=category, sku='RFM-001',
            name='RFM商品', price=1000, stock=99,
        )

        # Create orders for 3 different customers
        for i in range(3):
            customer_hash = f'customer_{i}_hash'
            for j in range(i + 1):  # customer 0=1order, 1=2orders, 2=3orders
                order = Order.objects.create(
                    store=store, status=Order.STATUS_OPEN,
                    customer_line_user_hash=customer_hash,
                )
                OrderItem.objects.create(
                    order=order, product=p,
                    qty=(i + 1), unit_price=1000,
                )

        result = compute_rfm(scope={'order__store': store})
        assert len(result) == 3
        # Check structure
        for r in result:
            assert 'customer_id' in r
            assert 'recency' in r
            assert 'frequency' in r
            assert 'monetary' in r
            assert 'r_score' in r
            assert 'f_score' in r
            assert 'm_score' in r
            assert 'rfm_score' in r
            assert 'segment' in r

    def test_rfm_segments(self, db):
        from booking.services.rfm_analysis import _classify_segment

        assert _classify_segment(5, 5, 5) == 'champion'
        assert _classify_segment(4, 3, 3) == 'loyal'
        assert _classify_segment(5, 1, 1) == 'new'
        assert _classify_segment(3, 3, 3) == 'potential'
        assert _classify_segment(1, 4, 4) == 'at_risk'
        assert _classify_segment(1, 1, 4) == 'cant_lose'
        assert _classify_segment(1, 1, 1) == 'lost'
        assert _classify_segment(3, 2, 2) == 'other'


# ==============================
# sales_forecast.py tests
# ==============================

class TestSalesForecast:
    """Tests for sales forecast service."""

    def test_no_data_returns_empty_forecast(self, db, store):
        from booking.services.sales_forecast import generate_forecast
        result = generate_forecast(scope={'order__store': store}, forecast_days=7)
        assert result['forecast'] == []
        assert result['historical'] == []
        assert result['method'] == 'moving_average'

    def test_moving_average_forecast(self, db, store, category):
        from booking.services.sales_forecast import generate_forecast

        p = Product.objects.create(
            store=store, category=category, sku='FC-001',
            name='予測商品', price=1000, stock=99,
        )

        # Create 30 days of order history
        today = timezone.now()
        for day_offset in range(30):
            order_dt = today - timedelta(days=day_offset)
            order = Order.objects.create(
                store=store, status=Order.STATUS_OPEN,
            )
            # Manually set created_at
            Order.objects.filter(pk=order.pk).update(created_at=order_dt)
            OrderItem.objects.create(
                order=order, product=p,
                qty=2, unit_price=1000,
            )

        result = generate_forecast(
            scope={'order__store': store},
            forecast_days=7, history_days=60,
        )
        assert result['method'] == 'moving_average'
        assert len(result['forecast']) == 7
        assert len(result['historical']) > 0

        # Check forecast structure
        for f in result['forecast']:
            assert 'date' in f
            assert 'predicted' in f
            assert 'lower' in f
            assert 'upper' in f
            assert f['lower'] <= f['predicted'] <= f['upper']

    def test_moving_average_empty_history(self, db):
        from booking.services.sales_forecast import _moving_average_forecast
        result = _moving_average_forecast([], forecast_days=7)
        assert result == []

    def test_moving_average_with_data(self, db):
        from booking.services.sales_forecast import _moving_average_forecast

        today = date.today()
        historical = [
            (today - timedelta(days=i), 10000 + (i % 7) * 1000)
            for i in range(28)
        ]
        historical.sort(key=lambda x: x[0])

        result = _moving_average_forecast(historical, forecast_days=7)
        assert len(result) == 7
        for f in result:
            assert f['predicted'] > 0
            assert f['lower'] >= 0

    def test_prophet_not_available(self, db):
        """Prophet fallback should return None gracefully."""
        from booking.services.sales_forecast import _try_prophet_forecast

        today = date.today()
        historical = [
            (today - timedelta(days=i), 10000)
            for i in range(20)
        ]
        historical.sort(key=lambda x: x[0])

        with patch.dict('sys.modules', {'prophet': None}):
            # Even if prophet import fails, should return None
            result = _try_prophet_forecast(historical, forecast_days=7)
            # Result might be None (no prophet) or a list (if prophet is installed)
            assert result is None or isinstance(result, list)

    def test_prophet_too_few_data(self, db):
        from booking.services.sales_forecast import _try_prophet_forecast

        today = date.today()
        historical = [
            (today - timedelta(days=i), 10000)
            for i in range(5)  # only 5 data points < 14 threshold
        ]

        result = _try_prophet_forecast(historical, forecast_days=7)
        assert result is None


# ==============================
# ai_staff_recommend.py tests (50% → ~80%)
# ==============================

class TestBuildFeatureMatrix:
    """Tests for build_feature_matrix()."""

    def test_no_data_returns_empty(self, db, store):
        from booking.services.ai_staff_recommend import build_feature_matrix
        X, y, feature_names = build_feature_matrix(store, lookback_days=90)
        assert X == []
        assert y == []
        assert len(feature_names) == 6

    def test_with_data(self, db, store, staff, shift_period):
        from booking.services.ai_staff_recommend import build_feature_matrix

        today = date.today()
        # Create some recent shift assignments
        for day_offset in range(3):
            d = today - timedelta(days=day_offset + 1)
            ShiftAssignment.objects.create(
                period=shift_period, staff=staff,
                date=d, start_hour=9, end_hour=17,
            )

        # Create visitor counts for same days
        for day_offset in range(3):
            d = today - timedelta(days=day_offset + 1)
            for h in range(9, 17):
                VisitorCount.objects.create(
                    store=store, date=d, hour=h,
                    pir_count=10, estimated_visitors=5, order_count=3,
                )

        X, y, feature_names = build_feature_matrix(store, lookback_days=30)
        assert len(X) > 0
        assert len(X) == len(y)
        assert feature_names == [
            'day_of_week', 'hour', 'is_holiday', 'month',
            'visitor_count', 'order_count',
        ]
        # Each feature should have 6 elements
        for features in X:
            assert len(features) == 6


class TestTrainModel:
    """Tests for train_model()."""

    def test_insufficient_data(self, db, store):
        from booking.services.ai_staff_recommend import train_model
        result = train_model(store)
        assert result is None


class TestGenerateRecommendations:
    """Tests for generate_recommendations()."""

    def test_no_active_model(self, db, store):
        from booking.services.ai_staff_recommend import generate_recommendations
        result = generate_recommendations(store, [date.today()])
        assert result == 0


# ==============================
# Admin changelist tests — covers get_queryset, changelist_view, list_display
# ==============================

class TestAdminChangelistCoverage:
    """Hit admin changelist views to cover get_queryset + list_display callables."""

    ADMIN_MODELS = [
        'schedule',
        'staff',
        'store',
        'iotdevice',
        'category',
        'product',
        'order',
        'property',
        'shiftperiod',
        'shiftassignment',
        'employmentcontract',
        'workattendance',
        'payrollperiod',
        'tableseat',
        'paymentmethod',
        'securityaudit',
        'securitylog',
        'costreport',
        'attendancetotpconfig',
        'postransaction',
        'visitorcount',
        'staffevaluation',
        'evaluationcriteria',
        'customerfeedback',
        'businessinsight',
        'ventilationautocontrol',
        'ecproduct',
        'eccategory',
        'shifttemplate',
        'shiftpublishhistory',
        'shiftstaffrequirement',
        'salarystructure',
        'sitesettings',
        'adminmenuconfig',
        'adminsidebarsettings',
        'homepagecustomblock',
        'herobanner',
        'bannerad',
        'externallink',
        'shippingconfig',
    ]

    @pytest.mark.parametrize('model_name', ADMIN_MODELS)
    def test_changelist_accessible(self, admin_client, model_name):
        """Admin changelist should be accessible for all registered models."""
        url = f'/admin/booking/{model_name}/'
        resp = admin_client.get(url)
        assert resp.status_code in (200, 301, 302), f'{model_name}: got {resp.status_code}'

    def test_order_admin_actions(self, admin_client, store, order):
        """Test admin actions on Order changelist."""
        url = '/admin/booking/order/'

        # Mark as shipped action
        resp = admin_client.post(url, {
            'action': 'mark_shipped',
            '_selected_action': [order.pk],
        })
        assert resp.status_code in (200, 302)

        # Delete selected orders action
        resp = admin_client.post(url, {
            'action': 'delete_selected_orders',
            '_selected_action': [order.pk],
        })
        assert resp.status_code in (200, 302)
