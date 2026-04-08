"""シフトAPI URLconf"""
from django.urls import path
from .views_shift_api import (
    ShiftWeekGridView,
    ShiftCellDetailView,
    ShiftAssignmentAPIView,
    ShiftApplyTemplateAPIView,
    ShiftTemplateAPIView,
    ShiftBulkAssignAPIView,
    ShiftAutoScheduleAPIView,
    ShiftPublishAPIView,
    ShiftChangeLogAPIView,
    ShiftRevokeAPIView,
    ShiftReopenAPIView,
    ShiftPeriodAPIView,
    StoreClosedDateAPIView,
    ShiftVacancyAPIView,
    ShiftVacancyApplyAPIView,
    ShiftSwapRequestAPIView,
)
from .views_shift_staff import StaffShiftRequestAPIView
from .views_shift_staffing_api import StaffingRequirementAPIView, StaffingOverrideAPIView

app_name = 'shift_api'

urlpatterns = [
    path('week-grid/', ShiftWeekGridView.as_view(), name='shift_week_grid'),
    path('detail/<int:pk>/', ShiftCellDetailView.as_view(), name='shift_cell_detail'),
    path('assignments/', ShiftAssignmentAPIView.as_view(), name='shift_assignment_create'),
    path('assignments/<int:pk>/', ShiftAssignmentAPIView.as_view(), name='shift_assignment_detail'),
    path('apply-template/', ShiftApplyTemplateAPIView.as_view(), name='shift_apply_template'),
    path('templates/', ShiftTemplateAPIView.as_view(), name='shift_template_list'),
    path('templates/<int:pk>/', ShiftTemplateAPIView.as_view(), name='shift_template_detail'),
    path('bulk-assign/', ShiftBulkAssignAPIView.as_view(), name='shift_bulk_assign'),
    path('auto-schedule/', ShiftAutoScheduleAPIView.as_view(), name='shift_auto_schedule'),
    path('publish/', ShiftPublishAPIView.as_view(), name='shift_publish'),
    path('change-logs/', ShiftChangeLogAPIView.as_view(), name='shift-change-logs'),
    path('revoke/', ShiftRevokeAPIView.as_view(), name='shift_revoke'),
    path('reopen/', ShiftReopenAPIView.as_view(), name='shift_reopen'),
    path('periods/', ShiftPeriodAPIView.as_view(), name='shift_period_create'),
    path('periods/<int:pk>/', ShiftPeriodAPIView.as_view(), name='shift_period_detail'),
    path('closed-dates/', StoreClosedDateAPIView.as_view(), name='closed_dates'),
    path('my-requests/', StaffShiftRequestAPIView.as_view(), name='my_shift_requests'),
    path('my-requests/<int:pk>/', StaffShiftRequestAPIView.as_view(), name='my_shift_request_detail'),
    # 不足枠
    path('vacancies/', ShiftVacancyAPIView.as_view(), name='shift_vacancies'),
    path('vacancies/<int:pk>/apply/', ShiftVacancyApplyAPIView.as_view(), name='shift_vacancy_apply'),
    # 交代・欠勤申請
    path('swap-requests/', ShiftSwapRequestAPIView.as_view(), name='shift_swap_requests'),
    path('swap-requests/<int:pk>/', ShiftSwapRequestAPIView.as_view(), name='shift_swap_request_detail'),
    # 必要人数設定
    path('staffing/', StaffingRequirementAPIView.as_view(), name='staffing_requirements'),
    path('staffing/overrides/', StaffingOverrideAPIView.as_view(), name='staffing_overrides'),
    path('staffing/overrides/<int:pk>/', StaffingOverrideAPIView.as_view(), name='staffing_override_detail'),
]
