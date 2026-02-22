from django import forms
from .models import Staff, AdminMenuConfig


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['name', 'thumbnail', 'introduction', 'price']


# モデルキー → わかりやすい日本語ラベル
MODEL_JAPANESE_LABELS = {
    'schedule': '予約スケジュール',
    'shiftperiod': 'シフト募集期間',
    'shiftrequest': 'シフト希望',
    'shiftassignment': '確定シフト',
    'staff': 'スタッフ',
    'store': '店舗',
    'storescheduleconfig': '店舗スケジュール設定',
    'category': '商品カテゴリ',
    'product': '商品',
    'producttranslation': '商品翻訳',
    'order': '注文',
    'iotdevice': 'IoTデバイス',
    'property': '物件',
    'propertydevice': '物件デバイス',
    'company': '運営会社情報',
    'notice': 'お知らせ',
    'media': 'メディア掲載',
    'sitesettings': 'サイト設定',
    'homepagecustomblock': 'カスタムブロック',
    'herobanner': 'ヒーローバナー',
    'bannerad': 'バナー広告',
    'externallink': '外部リンク',
    'systemconfig': 'システム設定',
    'admintheme': '管理画面テーマ',
    'dashboardlayout': 'ダッシュボードレイアウト',
    'adminmenuconfig': 'メニュー権限設定',
    'employmentcontract': '雇用契約',
    'workattendance': '勤怠記録',
    'payrollperiod': '給与計算期間',
    'payrollentry': '給与明細',
    'payrolldeduction': '控除明細',
    'salarystructure': '給与体系',
    'user': 'ユーザー',
    'group': 'グループ',
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
        label='表示許可メニュー',
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text='このロールに表示するメニュー項目にチェックを入れてください。',
    )

    class Meta:
        model = AdminMenuConfig
        fields = ['role', 'allowed_models']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['allowed_models'].choices = _build_model_choices()
        self.fields['role'].help_text = 'superuserは常に全メニューを表示するため設定不要です。'
        if self.instance and self.instance.pk:
            self.initial['allowed_models'] = self.instance.allowed_models or []
