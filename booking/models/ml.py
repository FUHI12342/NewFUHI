"""機械学習モデル: StaffRecommendationModel, StaffRecommendationResult"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class StaffRecommendationModel(models.Model):
    """学習済みMLモデル保存"""
    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='recommendation_models')
    model_file = models.FileField(_('モデルファイル'), upload_to='ml_models/')
    model_type = models.CharField(_('モデル種別'), max_length=50, default='random_forest')
    feature_names = models.JSONField(_('特徴量名'), default=list)
    accuracy_score = models.FloatField(_('精度スコア'), default=0)
    mae_score = models.FloatField(_('MAEスコア'), default=0)
    training_samples = models.IntegerField(_('学習サンプル数'), default=0)
    trained_at = models.DateTimeField(_('学習日時'), auto_now_add=True)
    is_active = models.BooleanField(_('有効'), default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('AI推薦モデル')
        verbose_name_plural = _('AI推薦モデル')
        ordering = ('-trained_at',)

    def __str__(self):
        return f'{self.store.name} {self.model_type} (MAE:{self.mae_score:.2f})'


class StaffRecommendationResult(models.Model):
    """AIスタッフ推薦結果"""
    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='recommendation_results')
    date = models.DateField(_('日付'))
    hour = models.IntegerField(_('時間帯'))  # 0-23
    recommended_staff_count = models.IntegerField(_('推薦スタッフ数'))
    confidence = models.FloatField(_('信頼度'), default=0)
    factors = models.JSONField(_('特徴量重要度'), default=dict)
    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('AI推薦結果')
        verbose_name_plural = _('AI推薦結果')
        unique_together = ('store', 'date', 'hour')

    def __str__(self):
        return f'{self.store.name} {self.date} {self.hour}時 推薦:{self.recommended_staff_count}人'
