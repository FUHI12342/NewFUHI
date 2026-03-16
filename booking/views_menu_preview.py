"""メニュープレビュー: 管理画面から最初のテーブルのメニューページへリダイレクト"""
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views import View

from booking.models import TableSeat, Store


class MenuPreviewRedirectView(View):
    """最初のアクティブテーブルの /t/{uuid}/ へリダイレクト"""

    def get(self, request):
        # ユーザーの店舗を特定
        store = None
        if request.user.is_superuser:
            store = Store.objects.first()
        else:
            try:
                store = request.user.staff.store
            except Exception:
                store = Store.objects.first()

        seat = TableSeat.objects.filter(
            store=store, is_active=True,
        ).order_by('label').first() if store else None

        if seat:
            return redirect(f'/t/{seat.id}/')

        return HttpResponse(
            '<p style="padding:40px;text-align:center;color:#666;">'
            'テーブルが登録されていません。先にテーブルを作成してください。'
            '</p>',
        )
