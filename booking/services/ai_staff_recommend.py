"""AIスタッフ推薦サービス - 機械学習によるシフト人員推薦"""
import logging
import os
import tempfile
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def build_feature_matrix(store, lookback_days=90):
    """特徴量マトリクスを構築する

    Features:
    - day_of_week (0-6)
    - hour (0-23)
    - is_holiday (0/1)
    - month (1-12)
    - visitor_count
    - order_count

    Target: actual staff count per hour
    """
    from booking.models import VisitorCount, ShiftAssignment

    date_from = date.today() - timedelta(days=lookback_days)

    # 祝日リスト
    holidays = set()
    public_holidays = getattr(settings, 'PUBLIC_HOLIDAYS', [])
    for h in public_holidays:
        holidays.add(h)

    X = []
    y = []

    visitor_data = {}
    for vc in VisitorCount.objects.filter(store=store, date__gte=date_from):
        visitor_data[(vc.date, vc.hour)] = (vc.estimated_visitors, vc.order_count)

    # 日付×時間帯ごとのスタッフ数を集計
    staff_counts = {}
    assignments = ShiftAssignment.objects.filter(
        period__store=store,
        date__gte=date_from,
    )
    for a in assignments:
        start_h = a.start_hour
        end_h = a.end_hour
        for h in range(start_h, end_h):
            key = (a.date, h)
            staff_counts[key] = staff_counts.get(key, 0) + 1

    # 特徴量構築
    current = date_from
    while current <= date.today():
        for hour in range(24):
            key = (current, hour)
            if key not in staff_counts:
                continue

            visitors, orders = visitor_data.get(key, (0, 0))

            features = [
                current.weekday(),
                hour,
                1 if current in holidays or current.weekday() == 6 else 0,
                current.month,
                visitors,
                orders,
            ]
            X.append(features)
            y.append(staff_counts[key])

        current += timedelta(days=1)

    feature_names = ['day_of_week', 'hour', 'is_holiday', 'month', 'visitor_count', 'order_count']
    return X, y, feature_names


def train_model(store):
    """RandomForestRegressorで学習しStaffRecommendationModelに保存

    Returns:
        StaffRecommendationModel or None
    """
    from booking.models import StaffRecommendationModel

    X, y, feature_names = build_feature_matrix(store)

    if len(X) < 10:
        logger.warning("Not enough training data for store %s (got %d samples)", store.name, len(X))
        return None

    try:
        from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
        from sklearn.model_selection import cross_val_score
        from sklearn.metrics import mean_absolute_error
        import joblib
        import numpy as np
    except ImportError:
        logger.error("scikit-learn or joblib not installed")
        return None

    X_arr = np.array(X)
    y_arr = np.array(y)

    # RandomForest vs GradientBoosting 比較
    models = {
        'random_forest': RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
        'gradient_boosting': GradientBoostingRegressor(n_estimators=100, random_state=42),
    }

    best_model = None
    best_mae = float('inf')
    best_type = 'random_forest'

    for name, model in models.items():
        scores = cross_val_score(model, X_arr, y_arr, cv=min(5, len(X)), scoring='neg_mean_absolute_error')
        mae = -scores.mean()
        logger.info("Model %s MAE: %.3f", name, mae)
        if mae < best_mae:
            best_mae = mae
            best_model = model
            best_type = name

    # 全データで再学習
    best_model.fit(X_arr, y_arr)

    # モデルファイル保存
    with tempfile.NamedTemporaryFile(suffix='.joblib', delete=False) as f:
        joblib.dump(best_model, f.name)
        temp_path = f.name

    try:
        from django.core.files import File
        # 既存モデルを非活性化
        StaffRecommendationModel.objects.filter(store=store, is_active=True).update(is_active=False)

        rec_model = StaffRecommendationModel(
            store=store,
            model_type=best_type,
            feature_names=feature_names,
            accuracy_score=0,
            mae_score=best_mae,
            training_samples=len(X),
            is_active=True,
        )
        with open(temp_path, 'rb') as f:
            rec_model.model_file.save(f'model_{store.id}_{best_type}.joblib', File(f), save=True)

        logger.info("Trained model for store %s: type=%s, MAE=%.3f, samples=%d",
                    store.name, best_type, best_mae, len(X))
        return rec_model
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def generate_recommendations(store, target_dates):
    """学習済みモデルで推論しStaffRecommendationResultに保存

    Args:
        store: Store instance
        target_dates: list of date objects

    Returns:
        int: 作成したレコード数
    """
    from booking.models import StaffRecommendationModel, StaffRecommendationResult, VisitorCount

    active_model = StaffRecommendationModel.objects.filter(
        store=store, is_active=True,
    ).first()

    if not active_model or not active_model.model_file:
        logger.warning("No active model for store %s", store.name)
        return 0

    try:
        import joblib
        import numpy as np
    except ImportError:
        logger.error("joblib not installed")
        return 0

    model = joblib.load(active_model.model_file.path)

    holidays = set(getattr(settings, 'PUBLIC_HOLIDAYS', []))

    count = 0
    for target_date in target_dates:
        # その日の来客データ（あれば）
        visitor_data = {}
        for vc in VisitorCount.objects.filter(store=store, date=target_date):
            visitor_data[vc.hour] = (vc.estimated_visitors, vc.order_count)

        for hour in range(24):
            visitors, orders = visitor_data.get(hour, (0, 0))

            features = np.array([[
                target_date.weekday(),
                hour,
                1 if target_date in holidays or target_date.weekday() == 6 else 0,
                target_date.month,
                visitors,
                orders,
            ]])

            prediction = model.predict(features)[0]
            recommended = max(0, round(prediction))

            # 特徴量重要度（RandomForest系のみ）
            factors = {}
            if hasattr(model, 'feature_importances_'):
                for name, importance in zip(active_model.feature_names, model.feature_importances_):
                    factors[name] = round(float(importance), 4)

            StaffRecommendationResult.objects.update_or_create(
                store=store,
                date=target_date,
                hour=hour,
                defaults={
                    'recommended_staff_count': recommended,
                    'confidence': float(getattr(model, 'score', lambda X, y: 0)(features, [recommended])) if hasattr(model, 'oob_score_') else 0.0,
                    'factors': factors,
                },
            )
            count += 1

    logger.info("Generated %d recommendations for store %s", count, store.name)
    return count
