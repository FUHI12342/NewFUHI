"""booking.models package — re-exports all models for backward compatibility."""
# Core models & constants
from .core import (  # noqa: F401
    LANG_CHOICES,
    STAFF_TYPE_CHOICES,
    Timer,
    Store,
    Staff,
    UserSerializer,
    Category,
    Product,
    ECCategory,
    ECProduct,
    ProductTranslation,
    SystemConfig,
    TableSeat,
    TaxServiceCharge,
    PaymentMethod,
)

# Schedule
from .schedule import Schedule  # noqa: F401

# Orders
from .orders import (  # noqa: F401
    Order,
    OrderItem,
    StockMovement,
    apply_stock_movement,
    POSTransaction,
    ShippingConfig,
)

# Shifts
from .shifts import (  # noqa: F401
    StoreScheduleConfig,
    ShiftPeriod,
    ShiftRequest,
    ShiftAssignment,
    ShiftTemplate,
    ShiftPublishHistory,
    ShiftChangeLog,
    StoreClosedDate,
    ShiftStaffRequirement,
    ShiftStaffRequirementOverride,
    ShiftVacancy,
    ShiftSwapRequest,
)

# IoT
from .iot import (  # noqa: F401
    IoTDevice,
    IoTEvent,
    VentilationAutoControl,
    IRCode,
    Property,
    PropertyDevice,
    PropertyAlert,
)

# HR
from .hr import (  # noqa: F401
    EvaluationCriteria,
    StaffEvaluation,
    EmploymentContract,
    WorkAttendance,
    PayrollPeriod,
    PayrollEntry,
    PayrollDeduction,
    SalaryStructure,
    AttendanceTOTPConfig,
    AttendanceStamp,
)

# CMS
from .cms import (  # noqa: F401
    Company,
    Notice,
    Media,
    HomepageCustomBlock,
    HeroBanner,
    BannerAd,
    ExternalLink,
)

# Admin config
from .admin_config import (  # noqa: F401
    DEFAULT_DASHBOARD_LAYOUT,
    LANGUAGE_CHOICES,
    DashboardLayout,
    AdminTheme,
    SiteSettings,
    AdminSidebarSettings,
    AdminMenuConfig,
)

# Analytics
from .analytics import (  # noqa: F401
    BusinessInsight,
    CustomerFeedback,
    VisitorCount,
    VisitorAnalyticsConfig,
    CostReport,
)

# Security
from .security import (  # noqa: F401
    SecurityAudit,
    SecurityLog,
)

# ML
from .ml import (  # noqa: F401
    StaffRecommendationModel,
    StaffRecommendationResult,
)

# Error reporting
from .error_reporting import ErrorReport  # noqa: F401

# Theme
from .theme import StoreTheme  # noqa: F401

# Page Layout
from .page_layout import (  # noqa: F401
    PageLayout,
    SectionSchema,
    DEFAULT_HOME_SECTIONS,
)

# Custom Pages
from .custom_page import CustomPage, PageTemplate, SavedBlock  # noqa: F401

# Social posting
from .social_posting import (  # noqa: F401
    SocialAccount,
    PostTemplate,
    PostHistory,
    KnowledgeEntry,
    DraftPost,
)

# LINE Customer
from .line_customer import LineCustomer, LineMessageLog  # noqa: F401

# Backup
from .backup import BackupConfig, BackupHistory  # noqa: F401
