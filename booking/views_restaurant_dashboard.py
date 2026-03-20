# booking/views_restaurant_dashboard.py
"""Backward-compatible re-exports from split dashboard modules.

Original 1557-line file split into:
  - views_dashboard_base.py      (utilities, mixins, DashboardLayoutAPIView)
  - views_dashboard_sales.py     (sales, menu eng, ABC, forecast, heatmap, AOV, channel)
  - views_dashboard_analytics.py (cohort, RFM, basket, CLV, visitor, insights)
  - views_dashboard_operations.py (staff, shift, stock, KPI, NPS, feedback, checkin, external)
"""

# Base
from .views_dashboard_base import (  # noqa: F401
    PERIOD_TRUNC_MAP,
    AdminSidebarMixin,
    DashboardAuthMixin,
    DashboardLayoutAPIView,
    RestaurantDashboardView,
    _clamp_int,
    _get_since_for_period,
    _parse_channel_filter,
)

# Sales
from .views_dashboard_sales import (  # noqa: F401
    ABCAnalysisAPIView,
    AOVTrendAPIView,
    ChannelSalesAPIView,
    MenuEngineeringAPIView,
    SalesAnalysisTextAPIView,
    SalesForecastAPIView,
    SalesHeatmapAPIView,
    SalesStatsAPIView,
)

# Analytics
from .views_dashboard_analytics import (  # noqa: F401
    BasketAnalysisAPIView,
    CLVAnalysisAPIView,
    CohortAnalysisAPIView,
    InsightsAPIView,
    RFMAnalysisAPIView,
    VisitorForecastAPIView,
)

# Operations
from .views_dashboard_operations import (  # noqa: F401
    AutoOrderRecommendationAPIView,
    CheckinStatsAPIView,
    CustomerFeedbackAPIView,
    ExternalDataAPIView,
    KPIScoreCardAPIView,
    LowStockAlertAPIView,
    NPSStatsAPIView,
    ReservationStatsAPIView,
    ShiftSummaryAPIView,
    StaffPerformanceAPIView,
)
