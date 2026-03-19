"""booking.admin package — re-exports all admin classes for backward compatibility."""
import logging

from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin
from django.utils.translation import gettext_lazy as _

from social_django.models import Association, Nonce, UserSocialAuth

from ..admin_site import custom_site
from ..models import TaxServiceCharge

logger = logging.getLogger(__name__)

# Import all admin submodules to trigger registration side effects
from .core import (  # noqa: F401
    ScheduleAdmin, StaffAdmin, StoreAdmin,
    StoreScheduleConfigInline, AdminThemeInline,
)
from .iot import (  # noqa: F401
    IoTDeviceAdmin, IoTEventAdmin, IRCodeAdmin,
    VentilationAutoControlAdmin, SystemConfigAdmin,
    PropertyAdmin, PropertyDeviceInline, PropertyAlertInline,
    IoTEventInline, IRCodeInline,
)
from .orders import (  # noqa: F401
    CategoryAdmin, ProductAdmin,
    ECCategoryAdmin, ECProductAdmin,
    OrderAdmin, OrderItemAdmin,
    StockMovementAdmin, ShippingConfigAdmin,
    ProductTranslationInline, OrderItemInline, ChannelGroupFilter,
)
from .shifts import (  # noqa: F401
    ShiftPeriodAdmin, ShiftRequestAdmin, ShiftAssignmentAdmin,
    ShiftChangeLogAdmin, ShiftVacancyAdmin, ShiftSwapRequestAdmin,
    ShiftTemplateAdmin, ShiftPublishHistoryAdmin,
    StoreClosedDateAdmin, ShiftStaffRequirementAdmin,
    ShiftStaffRequirementOverrideAdmin,
    ShiftRequestInline, ShiftAssignmentInline,
)
from .hr import (  # noqa: F401
    EmploymentContractAdmin, WorkAttendanceAdmin,
    PayrollPeriodAdmin, PayrollEntryAdmin,
    SalaryStructureAdmin, TableSeatAdmin,
    PaymentMethodAdmin, AttendanceTOTPConfigAdmin,
    AttendanceStampAdmin,
    PayrollDeductionInline, PayrollEntryInline,
)
from .cms import (  # noqa: F401
    NoticeAdmin, CompanyAdmin, MediaAdmin,
    SiteSettingsAdmin, AdminSidebarSettingsAdmin,
    HomepageCustomBlockAdmin, HeroBannerAdmin,
    BannerAdAdmin, ExternalLinkAdmin,
    AdminMenuConfigAdmin,
    SecurityAuditAdmin, SecurityLogAdmin, CostReportAdmin,
    POSTransactionAdmin,
    VisitorCountAdmin, VisitorAnalyticsConfigAdmin,
    StaffRecommendationModelAdmin, StaffRecommendationResultAdmin,
    BusinessInsightAdmin, CustomerFeedbackAdmin,
    EvaluationCriteriaAdmin, StaffEvaluationAdmin,
    TinyMCEWidget,
)
from .helpers import _is_owner_or_super  # noqa: F401


# Python Social Auth の非表示（不要なら管理画面から外す）
for m in (Association, Nonce, UserSocialAuth):
    try:
        admin.site.unregister(m)
    except admin.sites.NotRegistered:
        pass


# ==============================
# 税・サービス料
# ==============================
class TaxServiceChargeAdmin(admin.ModelAdmin):
    list_display = ('store', 'name', 'rate', 'is_active', 'applies_after_hour', 'sort_order')
    list_editable = ('rate', 'is_active', 'sort_order')
    list_filter = ('is_active', 'store')
    search_fields = ('name', 'store__name')


custom_site.register(TaxServiceCharge, TaxServiceChargeAdmin)


# User/Group も
class CustomUserAdmin(BaseUserAdmin):
    """「重要な日程」タブを除外したUserAdmin"""
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('個人情報'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('権限'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )


custom_site.register(User, CustomUserAdmin)
custom_site.register(Group, GroupAdmin)


logger.debug("booking.admin loaded")
