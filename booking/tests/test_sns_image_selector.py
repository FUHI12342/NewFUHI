"""sns_image_selector のユニットテスト"""
import datetime
from unittest.mock import MagicMock, patch

from django.core.files.base import ContentFile
from django.test import TestCase


class TestSelectImageForDraft(TestCase):
    """select_image_for_draft のテスト"""

    @patch('booking.models.shifts.ShiftAssignment')
    @patch('booking.models.Staff')
    def test_returns_staff_thumbnail_when_shift_exists(self, mock_staff_cls, mock_sa_cls):
        """当日出勤スタッフの thumbnail が返る"""
        from booking.services.sns_image_selector import select_image_for_draft

        mock_sa_cls.objects.filter.return_value.values_list.return_value.distinct.return_value = [1, 2]

        staff1 = MagicMock()
        staff1.pk = 1
        staff1.name = 'TestStaff'
        staff1.thumbnail = MagicMock()
        staff1.thumbnail.__bool__ = lambda self: True

        mock_staff_cls.objects.filter.return_value.exclude.return_value.order_by.return_value = [staff1]

        store = MagicMock()
        result = select_image_for_draft(store, target_date=datetime.date(2026, 4, 14))

        self.assertEqual(result, staff1.thumbnail)

    @patch('booking.models.shifts.ShiftAssignment')
    def test_falls_back_to_store_thumbnail(self, mock_sa_cls):
        """出勤スタッフに thumbnail がない場合、store.thumbnail にフォールバック"""
        from booking.services.sns_image_selector import select_image_for_draft

        mock_sa_cls.objects.filter.return_value.values_list.return_value.distinct.return_value = []

        store = MagicMock()
        store.thumbnail = MagicMock()
        store.thumbnail.__bool__ = lambda self: True
        store.name = 'TestStore'

        result = select_image_for_draft(store, target_date=datetime.date(2026, 4, 14))
        self.assertEqual(result, store.thumbnail)

    @patch('booking.models.shifts.ShiftAssignment')
    def test_returns_none_when_no_images(self, mock_sa_cls):
        """画像が一切ない場合 None が返る"""
        from booking.services.sns_image_selector import select_image_for_draft

        mock_sa_cls.objects.filter.return_value.values_list.return_value.distinct.return_value = []

        store = MagicMock()
        store.thumbnail = None
        store.photo_2 = None
        store.name = 'TestStore'

        result = select_image_for_draft(store, target_date=datetime.date(2026, 4, 14))
        self.assertIsNone(result)

    @patch('booking.models.shifts.ShiftAssignment')
    def test_deterministic_selection_by_date(self, mock_sa_cls):
        """同じ日なら同じスタッフが選択される"""
        from booking.services.sns_image_selector import select_image_for_draft

        mock_sa_cls.objects.filter.return_value.values_list.return_value.distinct.return_value = [1, 2, 3]

        staffs = []
        for i in range(3):
            s = MagicMock()
            s.pk = i + 1
            s.name = f'Staff{i}'
            s.thumbnail = MagicMock()
            s.thumbnail.__bool__ = lambda self: True
            staffs.append(s)

        target = datetime.date(2026, 4, 14)

        with patch('booking.models.Staff') as mock_staff_cls:
            mock_staff_cls.objects.filter.return_value.exclude.return_value.order_by.return_value = staffs

            store = MagicMock()
            r1 = select_image_for_draft(store, target_date=target)
            r2 = select_image_for_draft(store, target_date=target)

        self.assertEqual(r1, r2)


class TestAttachImageToDraft(TestCase):
    """attach_image_to_draft のテスト"""

    def test_copies_image_to_draft(self):
        """画像がコピーされて DraftPost.image に保存される"""
        from booking.services.sns_image_selector import attach_image_to_draft

        draft = MagicMock()
        image_field = MagicMock()
        image_field.name = 'thumbnails/test.jpg'
        image_field.read.return_value = b'fake-image-data'

        attach_image_to_draft(draft, image_field)

        image_field.open.assert_called_once_with('rb')
        image_field.read.assert_called_once()
        image_field.close.assert_called_once()
        draft.image.save.assert_called_once()
        args = draft.image.save.call_args
        self.assertEqual(args[0][0], 'test.jpg')
        self.assertIsInstance(args[0][1], ContentFile)

    def test_noop_when_no_image(self):
        """image_field が None の場合は何もしない"""
        from booking.services.sns_image_selector import attach_image_to_draft

        draft = MagicMock()
        attach_image_to_draft(draft, None)
        draft.image.save.assert_not_called()
