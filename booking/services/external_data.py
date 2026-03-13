# booking/services/external_data.py
"""外部データ連携スケルトン — 将来の外部API統合のプレースホルダー.

各関数はモックデータを返し、実装時の呼び出し先APIエンドポイントをログに記録する。
"""
import logging
from datetime import date, timedelta

from django.conf import settings

logger = logging.getLogger(__name__)

# 連携可能なサービス一覧
INTEGRATIONS = {
    'weather': {
        'name': '天気予報',
        'provider': 'OpenWeatherMap',
        'api_endpoint': 'https://api.openweathermap.org/data/2.5/forecast',
        'config_key': 'OPENWEATHERMAP_API_KEY',
        'description': '天気予報データを取得し、来客予測の精度を向上',
    },
    'google_reviews': {
        'name': 'Googleレビュー',
        'provider': 'Google Business Profile',
        'api_endpoint': 'https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews',
        'config_key': 'GOOGLE_BUSINESS_API_KEY',
        'description': 'Googleレビューを取得し、顧客フィードバック分析と連携',
    },
}


def get_integration_status():
    """全連携サービスの設定状態を返す.

    Returns:
        list of dicts with integration info and configured status
    """
    result = []
    for key, info in INTEGRATIONS.items():
        config_key = info['config_key']
        is_configured = bool(getattr(settings, config_key, None))
        result.append({
            'key': key,
            'name': info['name'],
            'provider': info['provider'],
            'description': info['description'],
            'configured': is_configured,
            'status': 'active' if is_configured else 'not_configured',
        })
    return result


def get_weather_forecast(lat=None, lng=None, days=7):
    """天気予報データを取得する.

    Args:
        lat: 緯度 (デフォルト: 東京)
        lng: 経度 (デフォルト: 東京)
        days: 予測日数

    Returns:
        dict with forecast data

    TODO: OpenWeatherMap API実装
        - API Key: settings.OPENWEATHERMAP_API_KEY
        - Endpoint: https://api.openweathermap.org/data/2.5/forecast
        - パラメータ: lat, lon, cnt, appid, units=metric, lang=ja
        - レスポンス: 3時間ごとの天気データ → 日次に集約
    """
    if lat is None:
        lat = 35.6762   # 東京
    if lng is None:
        lng = 139.6503

    api_key = getattr(settings, 'OPENWEATHERMAP_API_KEY', None)
    if api_key:
        # TODO: 実際のAPI呼び出し実装
        logger.info(
            f"OpenWeatherMap API call would be made to: "
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lng}&appid=***&units=metric&lang=ja"
        )

    logger.info("get_weather_forecast: モックデータを返却します")

    # モックデータ生成
    today = date.today()
    mock_forecast = []
    weather_patterns = [
        ('sunny', '晴れ', 22, 0),
        ('cloudy', '曇り', 20, 10),
        ('rainy', '雨', 18, 80),
        ('sunny', '晴れ', 24, 0),
        ('sunny', '晴れ', 23, 0),
        ('cloudy', '曇り', 19, 20),
        ('rainy', '雨', 17, 70),
    ]

    for i in range(days):
        pattern = weather_patterns[i % len(weather_patterns)]
        forecast_date = today + timedelta(days=i)
        mock_forecast.append({
            'date': forecast_date.isoformat(),
            'weather': pattern[0],
            'weather_label': pattern[1],
            'temperature_high': pattern[2] + (i % 3),
            'temperature_low': pattern[2] - 5,
            'precipitation_pct': pattern[3],
        })

    return {
        'location': {'lat': lat, 'lng': lng},
        'forecast': mock_forecast,
        'is_mock': True,
        'provider': 'OpenWeatherMap (mock)',
    }


def get_google_reviews(place_id=None):
    """Googleレビューデータを取得する.

    Args:
        place_id: Google Place ID

    Returns:
        dict with review data

    TODO: Google Business Profile API実装
        - API Key: settings.GOOGLE_BUSINESS_API_KEY
        - Endpoint: https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/reviews
        - OAuth 2.0認証が必要
        - レスポンス: レビュー一覧 (rating, comment, createTime, updateTime)
    """
    api_key = getattr(settings, 'GOOGLE_BUSINESS_API_KEY', None)
    if api_key and place_id:
        # TODO: 実際のAPI呼び出し実装
        logger.info(
            f"Google Business Profile API call would be made for place_id: {place_id}"
        )

    logger.info("get_google_reviews: モックデータを返却します")

    # モックデータ
    mock_reviews = [
        {
            'rating': 5,
            'comment': '雰囲気が素晴らしく、シーシャの種類も豊富でした。',
            'author': 'ユーザーA',
            'created_at': (date.today() - timedelta(days=2)).isoformat(),
        },
        {
            'rating': 4,
            'comment': 'スタッフの対応が丁寧で居心地が良かったです。',
            'author': 'ユーザーB',
            'created_at': (date.today() - timedelta(days=5)).isoformat(),
        },
        {
            'rating': 3,
            'comment': '少し混んでいましたが、味は良かったです。',
            'author': 'ユーザーC',
            'created_at': (date.today() - timedelta(days=10)).isoformat(),
        },
    ]

    return {
        'place_id': place_id or '(not configured)',
        'reviews': mock_reviews,
        'avg_rating': round(sum(r['rating'] for r in mock_reviews) / len(mock_reviews), 1),
        'total_reviews': len(mock_reviews),
        'is_mock': True,
        'provider': 'Google Business Profile (mock)',
    }
