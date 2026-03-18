from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Staff, AdminMenuConfig


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['name', 'thumbnail', 'introduction', 'price']


# モデルキー → わかりやすい日本語ラベル
MODEL_JAPANESE_LABELS = {
    'schedule': _('予約スケジュール'),
    'shiftperiod': _('シフト募集期間'),
    'shiftrequest': _('シフト希望'),
    'shiftassignment': _('確定シフト'),
    'staff': _('スタッフ'),
    'store': _('店舗'),
    'storescheduleconfig': _('店舗スケジュール設定'),
    'category': _('商品カテゴリ'),
    'product': _('商品'),
    'producttranslation': _('商品翻訳'),
    'order': _('注文'),
    'iotdevice': _('IoTデバイス'),
    'property': _('物件'),
    'propertydevice': _('物件デバイス'),
    'company': _('運営会社情報'),
    'notice': _('お知らせ'),
    'media': _('メディア掲載'),
    'sitesettings': _('サイト設定'),
    'homepagecustomblock': _('カスタムブロック'),
    'herobanner': _('ヒーローバナー'),
    'bannerad': _('バナー広告'),
    'externallink': _('外部リンク'),
    'systemconfig': _('システム設定'),
    'admintheme': _('管理画面テーマ'),
    'dashboardlayout': _('ダッシュボードレイアウト'),
    'adminmenuconfig': _('メニュー権限設定'),
    'employmentcontract': _('雇用契約'),
    'workattendance': _('勤怠記録'),
    'payrollperiod': _('給与計算期間'),
    'payrollentry': _('給与明細'),
    'payrolldeduction': _('控除明細'),
    'salarystructure': _('給与体系'),
    'user': _('ユーザー'),
    'group': _('グループ'),
}


def _build_model_choices():
    """GROUP_MAP の全モデルキーから choices を動的生成する（日本語ラベル付き）"""
    from .admin_site import GROUP_MAP
    choices = []
    seen = set()
    for group_name, model_keys in GROUP_MAP.items():
        for key in model_keys:
            if key in seen:
                continue
            seen.add(key)
            label = MODEL_JAPANESE_LABELS.get(key, key)
            choices.append((key, label))
    return choices


class AdminMenuConfigForm(forms.ModelForm):
    allowed_models = forms.MultipleChoiceField(
        label=_('表示許可メニュー'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_('このロールに表示するメニュー項目にチェックを入れてください。'),
    )

    class Meta:
        model = AdminMenuConfig
        fields = ['role', 'allowed_models']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['allowed_models'].choices = _build_model_choices()
        self.fields['role'].help_text = _('superuserは常に全メニューを表示するため設定不要です。')
        if self.instance and self.instance.pk:
            self.initial['allowed_models'] = self.instance.allowed_models or []
