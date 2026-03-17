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
    ShiftRevokeAPIView,
    ShiftReopenAPIView,
    ShiftPeriodAPIView,
    StoreClosedDateAPIView,
)
from .views_shift_staff import StaffShiftRequestAPIView

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
    path('revoke/', ShiftRevokeAPIView.as_view(), name='shift_revoke'),
    path('reopen/', ShiftReopenAPIView.as_view(), name='shift_reopen'),
    path('periods/', ShiftPeriodAPIView.as_view(), name='shift_period_create'),
    path('periods/<int:pk>/', ShiftPeriodAPIView.as_view(), name='shift_period_detail'),
    path('closed-dates/', StoreClosedDateAPIView.as_view(), name='closed_dates'),
    path('my-requests/', StaffShiftRequestAPIView.as_view(), name='my_shift_requests'),
    path('my-requests/<int:pk>/', StaffShiftRequestAPIView.as_view(), name='my_shift_request_detail'),
]
