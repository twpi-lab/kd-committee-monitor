"""주말 0건 장애 알림 판정 테스트"""
from datetime import datetime
from zoneinfo import ZoneInfo

from healthcheck import should_send_zero_crawl_alert

KST = ZoneInfo("Asia/Seoul")


def test_weekend_zero_crawl_does_not_send_alert():
    saturday = datetime(2026, 5, 30, 9, 0, tzinfo=KST)
    status = {"total_crawled": 0}

    assert should_send_zero_crawl_alert(status, now=saturday) is False


def test_weekday_zero_crawl_sends_alert():
    monday = datetime(2026, 6, 1, 9, 0, tzinfo=KST)
    status = {"total_crawled": 0}

    assert should_send_zero_crawl_alert(status, now=monday) is True


def test_weekday_nonzero_crawl_does_not_send_alert():
    monday = datetime(2026, 6, 1, 9, 0, tzinfo=KST)
    status = {"total_crawled": 5}

    assert should_send_zero_crawl_alert(status, now=monday) is False


def test_status_marked_weekend_suppresses_alert_even_if_now_is_weekday():
    monday = datetime(2026, 6, 1, 9, 0, tzinfo=KST)
    status = {"total_crawled": 0, "is_weekend": True}

    assert should_send_zero_crawl_alert(status, now=monday) is False
