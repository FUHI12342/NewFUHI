"""Japanese public holidays list.

Used by settings.PUBLIC_HOLIDAYS and referenced via django.conf.settings
throughout the booking app (calendar views, AI staff recommendation, etc.).
"""
import datetime

PUBLIC_HOLIDAYS = [
    # 2020
    datetime.date(2020, 1, 1),
    datetime.date(2020, 1, 13),
    datetime.date(2020, 2, 11),
    datetime.date(2020, 2, 23),
    datetime.date(2020, 2, 24),
    datetime.date(2020, 3, 20),
    datetime.date(2020, 4, 29),
    datetime.date(2020, 5, 3),
    datetime.date(2020, 5, 4),
    datetime.date(2020, 5, 5),
    datetime.date(2020, 7, 20),
    datetime.date(2020, 8, 11),
    datetime.date(2020, 9, 21),
    datetime.date(2020, 9, 22),
    datetime.date(2020, 10, 12),
    datetime.date(2020, 11, 3),
    datetime.date(2020, 11, 23),
    # 2021
    datetime.date(2021, 1, 1),
    datetime.date(2021, 1, 11),
    datetime.date(2021, 2, 11),
    datetime.date(2021, 2, 23),
    datetime.date(2021, 3, 20),
    datetime.date(2021, 4, 29),
    datetime.date(2021, 5, 3),
    datetime.date(2021, 5, 4),
    datetime.date(2021, 5, 5),
    datetime.date(2021, 7, 19),
    datetime.date(2021, 8, 11),
    datetime.date(2021, 9, 20),
    datetime.date(2021, 9, 23),
    datetime.date(2021, 10, 11),
    datetime.date(2021, 11, 3),
    datetime.date(2021, 11, 23),
]
