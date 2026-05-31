"""모니터링 실행 상태 기반 장애 알림 판정."""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def kst_now() -> datetime:
    """현재 시각을 KST timezone-aware datetime으로 반환."""
    return datetime.now(KST)


def is_weekend_kst(now: Optional[datetime] = None) -> bool:
    """KST 기준 토/일 여부."""
    current = now or kst_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)
    else:
        current = current.astimezone(KST)
    return current.weekday() >= 5


def should_send_zero_crawl_alert(status: dict, now: Optional[datetime] = None) -> bool:
    """전체 크롤링 0건 장애 알림 발송 여부.

    주말에는 공고가 정상적으로 없을 수 있으므로 0건이어도 장애 알림을 보내지 않는다.
    평일에는 이번 실행의 total_crawled가 0일 때만 장애 알림 대상이다.
    """
    if status.get("is_weekend") is True:
        return False
    if is_weekend_kst(now):
        return False
    try:
        total_crawled = int(status.get("total_crawled", 0))
    except (TypeError, ValueError):
        total_crawled = 0
    return total_crawled == 0
