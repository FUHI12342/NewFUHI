"""SNS OAuth 認証 + 下書き管理 URL設定"""
from django.urls import path

from booking.views_social_oauth import XConnectView, XCallbackView
from booking.views_social_drafts import (
    DraftListView, DraftEditView, DraftPostView,
    DraftScheduleView, DraftGenerateView, DraftRegenerateView,
)

urlpatterns = [
    # OAuth
    path('connect/x/', XConnectView.as_view(), name='social_connect_x'),
    path('callback/x/', XCallbackView.as_view(), name='social_callback_x'),

    # 下書き管理
    path('drafts/', DraftListView.as_view(), name='social_draft_list'),
    path('drafts/<int:pk>/edit/', DraftEditView.as_view(), name='social_draft_edit'),
    path('drafts/<int:pk>/post/', DraftPostView.as_view(), name='social_draft_post'),
    path('drafts/<int:pk>/schedule/', DraftScheduleView.as_view(), name='social_draft_schedule'),
    path('drafts/generate/', DraftGenerateView.as_view(), name='social_draft_generate'),
    path('drafts/<int:pk>/regenerate/', DraftRegenerateView.as_view(), name='social_draft_regenerate'),
]
