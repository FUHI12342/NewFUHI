from django import forms
from .models import Staff, AdminMenuConfig


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = ['name', 'thumbnail', 'introduction', 'price']


def _build_model_choices():
    """GROUP_MAP の全モデルキーから choices を動的生成する（verbose_name 付き）"""
    from .admin_site import GROUP_MAP, custom_site
    choices = []
    seen = set()
    for group_name, model_keys in GROUP_MAP.items():
        for key in model_keys:
            if key in seen:
                continue
            seen.add(key)
            # 登録済みモデルから verbose_name を取得
            label = key
            for model_cls, admin_cls in custom_site._registry.items():
                if model_cls.__name__.lower() == key:
                    label = f'{model_cls._meta.verbose_name} ({key})'
                    break
            choices.append((key, label))
    return choices


class AdminMenuConfigForm(forms.ModelForm):
    allowed_models = forms.MultipleChoiceField(
        label='表示許可モデル',
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = AdminMenuConfig
        fields = ['role', 'allowed_models']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['allowed_models'].choices = _build_model_choices()
        if self.instance and self.instance.pk:
            self.initial['allowed_models'] = self.instance.allowed_models or []

