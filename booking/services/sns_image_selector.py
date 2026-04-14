"""SNS投稿用画像の自動選択サービス"""
import logging

from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


def select_image_for_draft(store, target_date=None):
    """出勤キャストの thumbnail > store.thumbnail > None の優先順で画像選択

    Args:
        store: Store インスタンス
        target_date: 対象日 (None=今日)

    Returns:
        ImageFieldFile or None
    """
    from django.utils import timezone

    from booking.models.shifts import ShiftAssignment

    if target_date is None:
        target_date = timezone.localdate()

    # 当日出勤スタッフから thumbnail 付きを取得
    shift_staff_ids = (
        ShiftAssignment.objects.filter(store=store, date=target_date)
        .values_list('staff_id', flat=True)
        .distinct()
    )

    if shift_staff_ids:
        from booking.models import Staff

        staffs_with_thumb = list(
            Staff.objects.filter(
                pk__in=shift_staff_ids,
                thumbnail__isnull=False,
            )
            .exclude(thumbnail='')
            .order_by('pk')
        )

        if staffs_with_thumb:
            # deterministic selection based on date
            idx = target_date.toordinal() % len(staffs_with_thumb)
            selected = staffs_with_thumb[idx]
            logger.info(
                "Selected staff image: %s (staff_id=%d)", selected.name, selected.pk
            )
            return selected.thumbnail

    # fallback: store thumbnail
    if store.thumbnail:
        logger.info("Fallback to store thumbnail: store=%s", store.name)
        return store.thumbnail

    if hasattr(store, 'photo_2') and store.photo_2:
        logger.info("Fallback to store photo_2: store=%s", store.name)
        return store.photo_2

    logger.info("No image found for store=%s on %s", store.name, target_date)
    return None


def attach_image_to_draft(draft, image_field):
    """画像をコピーして DraftPost.image にセット（元画像を参照しない）

    Args:
        draft: DraftPost インスタンス
        image_field: ImageFieldFile (Staff.thumbnail / Store.thumbnail etc.)
    """
    if not image_field:
        return

    try:
        image_field.open('rb')
        content = image_field.read()
        image_field.close()

        filename = image_field.name.split('/')[-1]
        draft.image.save(filename, ContentFile(content), save=True)
        logger.info("Attached image '%s' to draft_id=%d", filename, draft.pk)
    except Exception:
        logger.exception("Failed to attach image to draft_id=%d", draft.pk)
