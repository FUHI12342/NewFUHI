"""Sales forecasting service.

Uses moving average with weekday coefficients as default method.
If `prophet` is installed, uses Prophet for seasonal/holiday-aware predictions.
"""
import logging
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Sum, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from booking.models import OrderItem

logger = logging.getLogger(__name__)


def _get_historical_daily(since, scope):
    """Return list of (date, revenue) sorted by date."""
    qs = (
        OrderItem.objects
        .filter(order__created_at__gte=since, **scope)
        .annotate(d=TruncDate('order__created_at'))
        .values('d')
        .annotate(revenue=Sum(F('qty') * F('unit_price')))
        .order_by('d')
    )
    return [(row['d'], row['revenue'] or 0) for row in qs]


def _moving_average_forecast(historical, forecast_days=14):
    """Forecast using 4-week moving average with weekday coefficients.

    1. Compute average daily revenue for last 28 days
    2. Compute weekday coefficients (Mon=0..Sun=6) from historical data
    3. Forecast = avg_daily * weekday_coefficient
    """
    if not historical:
        return []

    # Fill gaps in historical data
    first_date = historical[0][0]
    last_date = historical[-1][0]
    date_map = {d: rev for d, rev in historical}

    # Use last 28 days for baseline
    baseline_start = last_date - timedelta(days=27)
    if baseline_start < first_date:
        baseline_start = first_date

    # Weekday buckets
    weekday_totals = defaultdict(float)
    weekday_counts = defaultdict(int)
    overall_total = 0
    overall_count = 0

    current = baseline_start
    while current <= last_date:
        rev = date_map.get(current, 0)
        dow = current.weekday()
        weekday_totals[dow] += rev
        weekday_counts[dow] += 1
        overall_total += rev
        overall_count += 1
        current += timedelta(days=1)

    avg_daily = overall_total / overall_count if overall_count else 0

    # Weekday coefficients
    weekday_coef = {}
    for dow in range(7):
        if weekday_counts[dow] > 0:
            dow_avg = weekday_totals[dow] / weekday_counts[dow]
            weekday_coef[dow] = dow_avg / avg_daily if avg_daily > 0 else 1.0
        else:
            weekday_coef[dow] = 1.0

    # Generate forecast
    forecast = []
    for i in range(1, forecast_days + 1):
        forecast_date = last_date + timedelta(days=i)
        dow = forecast_date.weekday()
        predicted = avg_daily * weekday_coef[dow]
        # Confidence interval: ±30% as rough estimate
        lower = max(0, predicted * 0.7)
        upper = predicted * 1.3
        forecast.append({
            'date': forecast_date.isoformat(),
            'predicted': round(predicted),
            'lower': round(lower),
            'upper': round(upper),
        })

    return forecast


def _try_prophet_forecast(historical, forecast_days=14):
    """Attempt Prophet-based forecast. Returns None if prophet unavailable."""
    try:
        from prophet import Prophet
        import pandas as pd
    except ImportError:
        return None

    if len(historical) < 14:
        return None

    try:
        df = pd.DataFrame(historical, columns=['ds', 'y'])
        df['ds'] = pd.to_datetime(df['ds'])

        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
        )
        model.fit(df)

        future = model.make_future_dataframe(periods=forecast_days)
        prediction = model.predict(future)

        # Extract only forecast period
        forecast_rows = prediction.tail(forecast_days)
        forecast = []
        for _, row in forecast_rows.iterrows():
            forecast.append({
                'date': row['ds'].strftime('%Y-%m-%d'),
                'predicted': round(max(0, row['yhat'])),
                'lower': round(max(0, row['yhat_lower'])),
                'upper': round(max(0, row['yhat_upper'])),
            })
        return forecast
    except Exception as e:
        logger.warning(f"Prophet forecast failed: {e}")
        return None


def generate_forecast(scope, forecast_days=14, history_days=90):
    """Generate sales forecast.

    Args:
        scope: dict of filter kwargs for store scoping
        forecast_days: number of days to forecast
        history_days: number of days of history to use

    Returns:
        dict with 'historical', 'forecast', 'method' keys
    """
    since = timezone.now() - timedelta(days=history_days)
    historical = _get_historical_daily(since, scope)

    historical_list = [
        {'date': d.isoformat(), 'revenue': rev}
        for d, rev in historical
    ]

    # Try Prophet first
    forecast = _try_prophet_forecast(historical, forecast_days)
    method = 'prophet'

    # Fallback to moving average
    if forecast is None:
        forecast = _moving_average_forecast(historical, forecast_days)
        method = 'moving_average'

    return {
        'historical': historical_list,
        'forecast': forecast,
        'method': method,
    }
